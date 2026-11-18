//! Frozen context-band generalization measurement mirrored from
//! `agentrouter.evaluation.context_bands`.

use std::collections::HashMap;
use std::collections::{BTreeMap, BTreeSet};
use std::sync::OnceLock;

use agentrouter_classifier::{classify, ClassifyOptions};
use agentrouter_core::ContextBand;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::annotation_graph_signals::python_lowercase;
use crate::annotation_packs::PythonRandom;

pub const DEV_FILE: &str = "context_band_dev_v1.yaml";
pub const HOLDOUT_FILE: &str = "context_band_holdout_v1.yaml";
pub const HOLDOUT_SHA256: &str = "ca07dfa09f08cd877d383067b8e1163c0f196a5a1f0c4e641adefed12b17508f";
pub const BANDS: [&str; 3] = ["small", "medium", "large"];

const DEV_YAML: &str = include_str!("../../../agentrouter/benchmarks/context_band_dev_v1.yaml");
const HOLDOUT_YAML: &str =
    include_str!("../../../agentrouter/benchmarks/context_band_holdout_v1.yaml");
const REQUIRED_CATEGORIES: [&str; 9] = [
    "coding",
    "review",
    "audit",
    "refactor",
    "documentation",
    "analysis",
    "summarization",
    "data-pipeline",
    "ambiguous",
];
const BOOTSTRAP_SAMPLES: usize = 2_000;

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ContextBandCase {
    pub id: String,
    pub prompt: String,
    pub context_band: ContextBand,
    pub category: String,
}

#[derive(Deserialize)]
struct DatasetFile {
    cases: Vec<ContextBandCase>,
}

fn normalize(text: &str) -> String {
    static SPACES: OnceLock<Regex> = OnceLock::new();
    let lowered = python_lowercase(text.trim());
    let compact = SPACES
        .get_or_init(|| Regex::new(r"\s+").expect("whitespace regex"))
        .replace_all(&lowered, " ");
    compact
        .chars()
        .filter(|character| {
            character.is_alphanumeric() || *character == '_' || character.is_whitespace()
        })
        .collect()
}

fn digest_yaml(raw: &str) -> String {
    let normalized = raw.replace("\r\n", "\n").replace('\r', "\n");
    let digest = Sha256::digest(normalized.as_bytes());
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

pub fn load_cases_yaml(filename: &str, raw: &str) -> Result<Vec<ContextBandCase>, String> {
    if filename == HOLDOUT_FILE && digest_yaml(raw) != HOLDOUT_SHA256 {
        return Err(
            "frozen context-band holdout checksum changed; version the dataset and review it"
                .to_owned(),
        );
    }
    let parsed: DatasetFile = serde_yaml::from_str(raw).map_err(|error| error.to_string())?;
    let mut ids = BTreeSet::new();
    let mut prompts = BTreeSet::new();
    for case in &parsed.cases {
        if !ids.insert(case.id.clone()) || !prompts.insert(normalize(&case.prompt)) {
            return Err("duplicate id or prompt in context-band dataset".to_owned());
        }
        if !BANDS.contains(&band_name(case.context_band)) {
            return Err(format!("unknown context band in case: {}", case.id));
        }
    }
    Ok(parsed.cases)
}

/// Load either packaged dataset by the same public filename used by Python.
pub fn load_cases(filename: &str) -> Result<Vec<ContextBandCase>, String> {
    let raw = match filename {
        DEV_FILE => DEV_YAML,
        HOLDOUT_FILE => HOLDOUT_YAML,
        _ => return Err(format!("unknown context-band dataset: {filename}")),
    };
    load_cases_yaml(filename, raw)
}

/// Return Python `difflib.SequenceMatcher`'s Ratcliff/Obershelp ratio for
/// Unicode codepoint sequences, including its default popular-item heuristic.
fn sequence_ratio(left: &str, right: &str) -> f64 {
    let a = left.chars().collect::<Vec<_>>();
    let b = right.chars().collect::<Vec<_>>();
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    let mut b2j = HashMap::<char, Vec<usize>>::new();
    for (index, ch) in b.iter().enumerate() {
        b2j.entry(*ch).or_default().push(index);
    }
    let popular = if b.len() >= 200 {
        let threshold = b.len() / 100 + 1;
        b2j.iter()
            .filter(|(_, positions)| positions.len() > threshold)
            .map(|(ch, _)| *ch)
            .collect::<BTreeSet<_>>()
    } else {
        BTreeSet::new()
    };
    b2j.retain(|ch, _| !popular.contains(ch));

    let mut pending = vec![(0_usize, a.len(), 0_usize, b.len())];
    let mut blocks = Vec::<(usize, usize, usize)>::new();
    while let Some((alo, ahi, blo, bhi)) = pending.pop() {
        let mut best_i = alo;
        let mut best_j = blo;
        let mut best_size = 0;
        let mut previous = HashMap::<usize, usize>::new();
        for (i, ch) in a.iter().enumerate().take(ahi).skip(alo) {
            let mut current = HashMap::new();
            if let Some(positions) = b2j.get(ch) {
                for &j in positions.iter().filter(|j| **j >= blo && **j < bhi) {
                    let size = j
                        .checked_sub(1)
                        .and_then(|previous_j| previous.get(&previous_j).copied())
                        .unwrap_or(0)
                        + 1;
                    current.insert(j, size);
                    if size > best_size {
                        best_i = i + 1 - size;
                        best_j = j + 1 - size;
                        best_size = size;
                    }
                }
            }
            previous = current;
        }
        while best_i > alo && best_j > blo && a[best_i - 1] == b[best_j - 1] {
            best_i -= 1;
            best_j -= 1;
            best_size += 1;
        }
        while best_i + best_size < ahi
            && best_j + best_size < bhi
            && a[best_i + best_size] == b[best_j + best_size]
        {
            best_size += 1;
        }
        if best_size > 0 {
            blocks.push((best_i, best_j, best_size));
            if alo < best_i && blo < best_j {
                pending.push((alo, best_i, blo, best_j));
            }
            let aend = best_i + best_size;
            let bend = best_j + best_size;
            if aend < ahi && bend < bhi {
                pending.push((aend, ahi, bend, bhi));
            }
        }
    }
    blocks.sort_unstable();
    let mut matched = 0;
    let mut previous = None;
    for block in blocks {
        if let Some((ai, bj, size)) = previous {
            if ai + size == block.0 && bj + size == block.1 {
                previous = Some((ai, bj, size + block.2));
                continue;
            }
            matched += size;
        }
        previous = Some(block);
    }
    if let Some((_, _, size)) = previous {
        matched += size;
    }
    2.0 * matched as f64 / (a.len() + b.len()) as f64
}

pub fn prompt_similarity(left: &str, right: &str) -> Value {
    let a = normalize(left);
    let b = normalize(right);
    let at = a.split_whitespace().collect::<BTreeSet<_>>();
    let bt = b.split_whitespace().collect::<BTreeSet<_>>();
    let union = at.union(&bt).count();
    let jaccard = if union == 0 {
        1.0
    } else {
        at.intersection(&bt).count() as f64 / union as f64
    };
    json!({ "sequence": sequence_ratio(&a, &b), "token_jaccard": jaccard })
}

pub fn cross_split_leaks(
    holdout: &[ContextBandCase],
    references: &[(String, Vec<String>)],
) -> Vec<Value> {
    let mut leaks = Vec::new();
    for case in holdout {
        let normalized = normalize(&case.prompt);
        for (source, prompts) in references {
            for prompt in prompts {
                let other = normalize(prompt);
                let similarity = prompt_similarity(&case.prompt, prompt);
                let sequence = similarity["sequence"].as_f64().unwrap_or(0.0);
                let jaccard = similarity["token_jaccard"].as_f64().unwrap_or(0.0);
                let min_words = normalized
                    .split_whitespace()
                    .count()
                    .min(other.split_whitespace().count());
                let exact = normalized == other;
                let near = min_words >= 3 && (sequence >= 0.88 || jaccard >= 0.82);
                if exact || near {
                    leaks.push(json!({
                        "holdout_id": case.id,
                        "source": source,
                        "exact": exact,
                        "sequence": round4(sequence),
                        "token_jaccard": round4(jaccard),
                    }));
                }
            }
        }
    }
    leaks
}

pub fn load_development() -> Result<Vec<ContextBandCase>, String> {
    load_cases(DEV_FILE)
}

pub fn load_holdout() -> Result<Vec<ContextBandCase>, String> {
    let cases = load_cases(HOLDOUT_FILE)?;
    let categories = cases
        .iter()
        .map(|case| case.category.as_str())
        .collect::<BTreeSet<_>>();
    let missing = REQUIRED_CATEGORIES
        .iter()
        .filter(|category| !categories.contains(**category))
        .copied()
        .collect::<Vec<_>>();
    if !missing.is_empty() {
        return Err(format!(
            "holdout is missing required categories: {}",
            missing.join(", ")
        ));
    }
    Ok(cases)
}

fn band_name(band: ContextBand) -> &'static str {
    match band {
        ContextBand::Small => "small",
        ContextBand::Medium => "medium",
        ContextBand::Large => "large",
    }
}

fn round4(value: f64) -> f64 {
    agentrouter_routing::round_half_even(value, 4)
}

fn wilson(successes: usize, total: usize) -> [f64; 2] {
    if total == 0 {
        return [0.0, 0.0];
    }
    let z = 1.96_f64;
    let p = successes as f64 / total as f64;
    let denominator = 1.0 + z * z / total as f64;
    let center = (p + z * z / (2.0 * total as f64)) / denominator;
    let margin =
        z * ((p * (1.0 - p) + z * z / (4.0 * total as f64)) / total as f64).sqrt() / denominator;
    [
        round4((center - margin).max(0.0)),
        round4((center + margin).min(1.0)),
    ]
}

fn metric_values(pairs: &[(ContextBand, ContextBand)]) -> (f64, f64, [f64; 3]) {
    let bands = [ContextBand::Small, ContextBand::Medium, ContextBand::Large];
    let mut tp = [0_usize; 3];
    let mut fp = [0_usize; 3];
    let mut fn_count = [0_usize; 3];
    let mut correct = 0;
    for (expected, predicted) in pairs {
        let expected_index = bands.iter().position(|band| band == expected).unwrap();
        let predicted_index = bands.iter().position(|band| band == predicted).unwrap();
        if expected == predicted {
            correct += 1;
            tp[expected_index] += 1;
        } else {
            fn_count[expected_index] += 1;
            fp[predicted_index] += 1;
        }
    }
    let mut recalls = [0.0; 3];
    let mut f1_sum = 0.0;
    for index in 0..3 {
        let precision = if tp[index] + fp[index] == 0 {
            0.0
        } else {
            tp[index] as f64 / (tp[index] + fp[index]) as f64
        };
        let recall = if tp[index] + fn_count[index] == 0 {
            0.0
        } else {
            tp[index] as f64 / (tp[index] + fn_count[index]) as f64
        };
        recalls[index] = recall;
        f1_sum += if precision + recall == 0.0 {
            0.0
        } else {
            2.0 * precision * recall / (precision + recall)
        };
    }
    (correct as f64 / pairs.len() as f64, f1_sum / 3.0, recalls)
}

fn bootstrap_macro_f1(pairs: &[(ContextBand, ContextBand)]) -> Result<[f64; 2], String> {
    let mut rng = PythonRandom::new("1729")?;
    let mut values = Vec::with_capacity(BOOTSTRAP_SAMPLES);
    for _ in 0..BOOTSTRAP_SAMPLES {
        let mut sampled = Vec::with_capacity(pairs.len());
        for _ in pairs {
            sampled.push(pairs[rng.randbelow(pairs.len())]);
        }
        values.push(metric_values(&sampled).1);
    }
    values.sort_by(f64::total_cmp);
    Ok([
        round4(values[(0.025 * BOOTSTRAP_SAMPLES as f64) as usize]),
        round4(values[(0.975 * BOOTSTRAP_SAMPLES as f64) as usize - 1]),
    ])
}

pub fn score<F>(cases: &[ContextBandCase], predictor: F) -> Result<Value, String>
where
    F: Fn(&str) -> ContextBand,
{
    if cases.is_empty() {
        return Err("context-band score requires at least one case".to_owned());
    }
    let mut pairs = Vec::with_capacity(cases.len());
    let mut failures = Vec::new();
    let mut category_totals = BTreeMap::<String, usize>::new();
    let mut category_hits = BTreeMap::<String, usize>::new();
    let mut confusion = BTreeMap::<String, BTreeMap<String, usize>>::new();
    let mut band_totals = BTreeMap::<String, usize>::new();
    let mut band_hits = BTreeMap::<String, usize>::new();
    for case in cases {
        let predicted = predictor(&case.prompt);
        let expected = case.context_band;
        pairs.push((expected, predicted));
        let expected_name = band_name(expected).to_owned();
        let predicted_name = band_name(predicted).to_owned();
        *band_totals.entry(expected_name.clone()).or_default() += 1;
        *category_totals.entry(case.category.clone()).or_default() += 1;
        *confusion
            .entry(expected_name.clone())
            .or_default()
            .entry(predicted_name.clone())
            .or_default() += 1;
        if expected == predicted {
            *band_hits.entry(expected_name).or_default() += 1;
            *category_hits.entry(case.category.clone()).or_default() += 1;
        } else {
            failures.push(json!({
                "id": case.id,
                "category": case.category,
                "expected": band_name(expected),
                "predicted": band_name(predicted),
            }));
        }
    }
    let (accuracy, macro_f1, recalls) = metric_values(&pairs);
    let mut per_band_recall = serde_json::Map::new();
    let mut per_band_recall_ci95 = serde_json::Map::new();
    let mut confusion_json = serde_json::Map::new();
    for (index, band) in BANDS.iter().enumerate() {
        let total = band_totals.get(*band).copied().unwrap_or(0);
        let hits = band_hits.get(*band).copied().unwrap_or(0);
        per_band_recall.insert((*band).to_owned(), json!(round4(recalls[index])));
        per_band_recall_ci95.insert((*band).to_owned(), json!(wilson(hits, total)));
        confusion_json.insert(
            (*band).to_owned(),
            json!(confusion.get(*band).cloned().unwrap_or_default()),
        );
    }
    let category_accuracy = category_totals
        .iter()
        .map(|(category, total)| {
            (
                category.clone(),
                json!(round4(
                    category_hits.get(category).copied().unwrap_or(0) as f64 / *total as f64
                )),
            )
        })
        .collect::<serde_json::Map<_, _>>();
    Ok(json!({
        "n": cases.len(),
        "accuracy": round4(accuracy),
        "accuracy_ci95": wilson(cases.len() - failures.len(), cases.len()),
        "macro_f1": round4(macro_f1),
        "macro_f1_bootstrap_ci95": bootstrap_macro_f1(&pairs)?,
        "per_band_recall": per_band_recall,
        "per_band_recall_ci95": per_band_recall_ci95,
        "category_accuracy": category_accuracy,
        "confusion": confusion_json,
        "failures": failures,
    }))
}

pub fn legacy_pre_task004_band(prompt: &str) -> ContextBand {
    static TOKEN_K: OnceLock<Regex> = OnceLock::new();
    static TOKEN_PLAIN: OnceLock<Regex> = OnceLock::new();
    static DOCUMENT: OnceLock<Regex> = OnceLock::new();
    static EXISTING_CODE: OnceLock<Regex> = OnceLock::new();
    let text = prompt.to_lowercase();
    let token_k = TOKEN_K.get_or_init(|| Regex::new(r"(?i)(\d+)\s*k[\s-]*token").unwrap());
    let token_plain = TOKEN_PLAIN.get_or_init(|| Regex::new(r"(?i)(\d{4,})[\s-]*token").unwrap());
    let document = DOCUMENT.get_or_init(|| {
        Regex::new(r"(?i)\b(document|report|filing|book|transcript|pdf)\b").unwrap()
    });
    let existing_code = EXISTING_CODE.get_or_init(|| {
        Regex::new(r"(?i)\b(codebase|repo|repository|module|files|project|system|endpoint|endpoints|package|service|microservice|middleware|controller|handler|webhook|worker|parser|api|migration|pull request|test coverage|coverage|the auth|the payment)\b").unwrap()
    });
    let tokens = if let Some(capture) = token_k.captures(&text) {
        capture[1]
            .parse::<i64>()
            .unwrap_or(i64::MAX)
            .saturating_mul(1_000)
    } else if let Some(capture) = token_plain.captures(&text) {
        capture[1].parse::<i64>().unwrap_or(i64::MAX)
    } else if document.is_match(&text) {
        30_000
    } else if existing_code.is_match(&text) {
        12_000
    } else {
        2_000
    };
    if tokens < 8_000 {
        ContextBand::Small
    } else if tokens < 64_000 {
        ContextBand::Medium
    } else {
        ContextBand::Large
    }
}

pub fn evaluate_generalization() -> Result<Value, String> {
    let development = load_development()?;
    let holdout = load_holdout()?;
    let before = score(&holdout, legacy_pre_task004_band)?;
    let current = score(&holdout, |prompt| {
        classify(prompt, &ClassifyOptions::default()).context_band
    })?;
    let development_score = score(&development, |prompt| {
        classify(prompt, &ClassifyOptions::default()).context_band
    })?;
    Ok(json!({
        "schema_version": 1,
        "holdout_sha256": HOLDOUT_SHA256,
        "development": development_score,
        "pre_task004_holdout": before,
        "current_holdout": current,
        "delta": {
            "accuracy": round4(current["accuracy"].as_f64().unwrap_or(0.0) - before["accuracy"].as_f64().unwrap_or(0.0)),
            "macro_f1": round4(current["macro_f1"].as_f64().unwrap_or(0.0) - before["macro_f1"].as_f64().unwrap_or(0.0)),
        },
        "limitations": [
            "The holdout is public and model-assisted, pending independent human review.",
            "Context-band labels infer required input size from short prompts without real files.",
            "Confidence intervals quantify sample uncertainty, not annotation uncertainty."
        ]
    }))
}
