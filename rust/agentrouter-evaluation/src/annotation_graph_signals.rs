//! Optional Graphify repository-impact signal mirrored from
//! `agentrouter.annotation.graph_signals`.

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::path::Path;
use std::sync::{Arc, Mutex, OnceLock};

use regex::Regex;
use serde::Serialize;
use serde_json::Value;
use unicode_general_category::{get_general_category, GeneralCategory};

pub const DEFAULT_GRAPH_PATH: &str = "graphify-out/graph.json";
const GRAPH_CACHE_SIZE: usize = 4;

#[derive(Debug, Clone)]
struct GraphData {
    names: BTreeSet<String>,
    adjacency: BTreeMap<String, Vec<String>>,
}

type GraphCache = VecDeque<(String, Option<Arc<GraphData>>)>;

fn graph_cache() -> &'static Mutex<GraphCache> {
    static CACHE: OnceLock<Mutex<GraphCache>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(VecDeque::new()))
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct ImpactSignal {
    pub available: bool,
    pub matched_nodes: usize,
    pub dependency_reach: usize,
    pub feature: f64,
}

impl ImpactSignal {
    fn unavailable() -> Self {
        Self {
            available: false,
            matched_nodes: 0,
            dependency_reach: 0,
            feature: 0.0,
        }
    }
}

/// Best-effort graph signal. Missing, unreadable, or invalid JSON files yield
/// the same text-only fallback as Python; malformed collection shapes error.
pub fn impact_for(prompt: &str, graph_path: impl AsRef<Path>) -> Result<ImpactSignal, String> {
    let key = graph_path.as_ref().to_string_lossy().into_owned();
    let Some(graph) = load_graph(&key)? else {
        return Ok(ImpactSignal::unavailable());
    };
    let tokens = Regex::new(r"(?i-u)[A-Za-z_][A-Za-z0-9_.-]{2,}")
        .expect("constant token regex")
        .find_iter(prompt)
        .map(|m| python_lowercase(m.as_str()))
        .collect::<BTreeSet<_>>();
    let matched = tokens
        .intersection(&graph.names)
        .cloned()
        .collect::<BTreeSet<_>>();
    let mut reached = matched.clone();
    for node in &matched {
        if let Some(neighbors) = graph.adjacency.get(node) {
            reached.extend(neighbors.iter().cloned());
        }
    }
    let dependency_reach = reached.len();
    Ok(ImpactSignal {
        available: true,
        matched_nodes: matched.len(),
        dependency_reach,
        feature: (dependency_reach as f64 / 20.0).min(1.0),
    })
}

fn load_graph(path: &str) -> Result<Option<Arc<GraphData>>, String> {
    {
        let mut cache = graph_cache()
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if let Some(index) = cache.iter().position(|(key, _)| key == path) {
            let cached = cache.remove(index).expect("located cache entry");
            let result = cached.1.clone();
            cache.push_front(cached);
            return Ok(result);
        }
    }

    let loaded = (|| {
        let Ok(text) = std::fs::read_to_string(path) else {
            return Ok(None);
        };
        let Ok(raw) = serde_json::from_str::<Value>(&text) else {
            return Ok(None);
        };
        let Some(object) = raw.as_object() else {
            return Err("graph root must be a JSON object".to_owned());
        };

        let mut names = BTreeSet::new();
        for node in python_iterable(object.get("nodes"), "nodes")? {
            let Some(node) = node.as_object() else {
                continue;
            };
            for key in ["name", "id", "label", "file"] {
                let Some(value) = node.get(key).and_then(Value::as_str) else {
                    continue;
                };
                if !value.is_empty() {
                    let basename = value.rsplit('/').next().unwrap_or(value);
                    names.insert(python_lowercase(
                        basename.split('.').next().unwrap_or(basename),
                    ));
                }
            }
        }

        let edges = object
            .get("edges")
            .filter(|value| is_truthy(value))
            .or_else(|| object.get("links"));
        let mut adjacency: BTreeMap<String, Vec<String>> = BTreeMap::new();
        for edge in python_iterable(edges, "edges")? {
            let Some(edge) = edge.as_object() else {
                continue;
            };
            let (Some(source), Some(target)) = (
                edge.get("source").and_then(Value::as_str),
                edge.get("target").and_then(Value::as_str),
            ) else {
                continue;
            };
            adjacency
                .entry(python_lowercase(source))
                .or_default()
                .push(python_lowercase(target));
        }
        Ok(Some(Arc::new(GraphData { names, adjacency })))
    })();

    if let Ok(value) = &loaded {
        let mut cache = graph_cache()
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if let Some(index) = cache.iter().position(|(key, _)| key == path) {
            cache.remove(index);
        }
        cache.push_front((path.to_owned(), value.clone()));
        while cache.len() > GRAPH_CACHE_SIZE {
            cache.pop_back();
        }
    }
    loaded
}

fn is_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(value) => value.as_f64().is_some_and(|number| number != 0.0),
        Value::String(value) => !value.is_empty(),
        Value::Array(value) => !value.is_empty(),
        Value::Object(value) => !value.is_empty(),
    }
}

/// Match Python `str.lower()`'s context-sensitive Greek final sigma rule.
fn python_lowercase(value: &str) -> String {
    let characters = value.chars().collect::<Vec<_>>();
    let mut output = String::with_capacity(value.len());
    for (index, character) in characters.iter().copied().enumerate() {
        if character != '\u{03a3}' {
            output.extend(character.to_lowercase());
            continue;
        }
        let preceded_by_cased = characters[..index]
            .iter()
            .rev()
            .copied()
            .find(|candidate| !is_case_ignorable(*candidate))
            .is_some_and(is_cased);
        let followed_by_cased = characters[index + 1..]
            .iter()
            .copied()
            .find(|candidate| !is_case_ignorable(*candidate))
            .is_some_and(is_cased);
        output.push(if preceded_by_cased && !followed_by_cased {
            '\u{03c2}'
        } else {
            '\u{03c3}'
        });
    }
    output
}

fn is_cased(character: char) -> bool {
    character.is_lowercase()
        || character.is_uppercase()
        || get_general_category(character) == GeneralCategory::TitlecaseLetter
}

fn is_case_ignorable(character: char) -> bool {
    matches!(
        get_general_category(character),
        GeneralCategory::NonspacingMark
            | GeneralCategory::EnclosingMark
            | GeneralCategory::Format
            | GeneralCategory::ModifierLetter
            | GeneralCategory::ModifierSymbol
    ) || matches!(
        character,
        '\'' | '\u{00b7}' | '\u{0387}' | '\u{05f3}' | '\u{05f4}' | '\u{2019}'
    )
}

fn python_iterable(value: Option<&Value>, field: &str) -> Result<Vec<Value>, String> {
    let Some(value) = value.filter(|value| is_truthy(value)) else {
        return Ok(Vec::new());
    };
    match value {
        Value::Array(values) => Ok(values.clone()),
        Value::String(value) => Ok(value
            .chars()
            .map(|character| Value::String(character.to_string()))
            .collect()),
        Value::Object(values) => Ok(values.keys().cloned().map(Value::String).collect()),
        Value::Null | Value::Bool(_) | Value::Number(_) => {
            Err(format!("graph {field} must be iterable"))
        }
    }
}

pub fn impact_for_default(prompt: &str) -> Result<ImpactSignal, String> {
    impact_for(prompt, DEFAULT_GRAPH_PATH)
}
