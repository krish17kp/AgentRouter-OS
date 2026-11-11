//! Optional Graphify repository-impact signal mirrored from
//! `agentrouter.annotation.graph_signals`.

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use regex::Regex;
use serde::Serialize;
use serde_json::Value;

pub const DEFAULT_GRAPH_PATH: &str = "graphify-out/graph.json";

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
    let Ok(text) = std::fs::read_to_string(graph_path) else {
        return Ok(ImpactSignal::unavailable());
    };
    let Ok(raw) = serde_json::from_str::<Value>(&text) else {
        return Ok(ImpactSignal::unavailable());
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
                names.insert(
                    basename
                        .split('.')
                        .next()
                        .unwrap_or(basename)
                        .to_lowercase(),
                );
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
            .entry(source.to_lowercase())
            .or_default()
            .push(target.to_lowercase());
    }

    // Python's expression is explicitly ASCII despite lowercasing matches.
    let tokens = Regex::new(r"(?i-u)[A-Za-z_][A-Za-z0-9_.-]{2,}")
        .expect("constant token regex")
        .find_iter(prompt)
        .map(|m| m.as_str().to_lowercase())
        .collect::<BTreeSet<_>>();
    let matched = tokens
        .intersection(&names)
        .cloned()
        .collect::<BTreeSet<_>>();
    let mut reached = matched.clone();
    for node in &matched {
        if let Some(neighbors) = adjacency.get(node) {
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
