//! Pure evaluation metric aggregation, ported from
//! `agentrouter/evaluation/metrics.py`.
//!
//! Predictions are supplied by the caller so the scorer can be differentially
//! checked offline without running a model or changing evaluation labels.

use std::collections::{BTreeMap, BTreeSet};

use agentrouter_routing::round_half_even;
use serde::{Deserialize, Serialize};

pub const SINGLE_DIMS: [&str; 6] = [
    "task_type",
    "complexity",
    "risk",
    "output",
    "context",
    "approval",
];

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct MetricCase {
    pub id: String,
    pub prompt: String,
    #[serde(default)]
    pub expected: BTreeMap<String, Vec<String>>,
    #[serde(default)]
    pub predicted: BTreeMap<String, String>,
    #[serde(default)]
    pub expected_tools: Vec<String>,
    #[serde(default)]
    pub predicted_tools: Vec<String>,
}

/// The evaluation-provenance fields required to compute `dataset_quality`.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct QualityCase {
    pub task_hash: String,
    #[serde(default)]
    pub paraphrase_group: Option<String>,
    #[serde(default)]
    pub source_split: Option<String>,
    #[serde(default = "default_language")]
    pub language: String,
    #[serde(default)]
    pub domain: Option<String>,
    #[serde(default)]
    pub risk: Option<String>,
    #[serde(default)]
    pub task_type: Option<String>,
    #[serde(default = "default_provenance_method")]
    pub provenance_method: String,
}

fn default_language() -> String {
    "en".to_owned()
}

fn default_provenance_method() -> String {
    "model_assisted".to_owned()
}

/// Mirror the dataset-quality aggregation in `evaluation.provenance`.
/// Environment metadata is intentionally separate because its values are
/// runtime- and platform-specific rather than dataset-derived.
pub fn dataset_quality(cases: &[QualityCase]) -> serde_json::Value {
    let mut hashes = BTreeSet::new();
    let mut family_splits = BTreeMap::<String, BTreeSet<String>>::new();
    let mut languages = BTreeMap::<String, usize>::new();
    let mut domains = BTreeMap::<String, usize>::new();
    let mut risks = BTreeMap::<String, usize>::new();
    let mut task_types = BTreeMap::<String, usize>::new();
    let mut provenance = BTreeMap::<String, usize>::new();
    for case in cases {
        hashes.insert(case.task_hash.as_str());
        if let Some(group) = case
            .paraphrase_group
            .as_deref()
            .filter(|group| !group.is_empty())
        {
            let split = case
                .source_split
                .as_deref()
                .filter(|split| !split.is_empty())
                .unwrap_or("default");
            family_splits
                .entry(group.to_owned())
                .or_default()
                .insert(split.to_owned());
        }
        *languages.entry(case.language.clone()).or_default() += 1;
        if let Some(domain) = case.domain.as_deref() {
            *domains.entry(domain.to_owned()).or_default() += 1;
        }
        if let Some(risk) = case.risk.as_deref() {
            *risks.entry(risk.to_owned()).or_default() += 1;
        }
        if let Some(task_type) = case.task_type.as_deref() {
            *task_types.entry(task_type.to_owned()).or_default() += 1;
        }
        *provenance
            .entry(case.provenance_method.clone())
            .or_default() += 1;
    }
    let leaked: Vec<_> = family_splits
        .iter()
        .filter_map(|(family, splits)| (splits.len() > 1).then_some(family.clone()))
        .collect();
    serde_json::json!({
        "n_cases": cases.len(),
        "exact_duplicates": cases.len() - hashes.len(),
        "paraphrase_families": family_splits.len(),
        "leaked_paraphrase_families": leaked,
        "language_distribution": languages,
        "domain_distribution": domains,
        "risk_distribution": risks,
        "task_type_distribution": task_types,
        "provenance_distribution": provenance,
        "model_assisted_count": cases.iter().filter(|case| case.provenance_method == "model_assisted").count(),
    })
}

#[derive(Debug, Clone)]
struct Pair {
    acceptable: Vec<String>,
    predicted: String,
}

fn rounded(value: f64) -> f64 {
    round_half_even(value, 4)
}

fn score_single(pairs: &[Pair]) -> serde_json::Value {
    let (mut tp, mut fp, mut fn_count) = (
        BTreeMap::<String, usize>::new(),
        BTreeMap::<String, usize>::new(),
        BTreeMap::<String, usize>::new(),
    );
    let mut correct = 0usize;
    for pair in pairs {
        if pair.acceptable.contains(&pair.predicted) {
            correct += 1;
            *tp.entry(pair.predicted.clone()).or_default() += 1;
        } else if let Some(gold) = pair.acceptable.first() {
            *fn_count.entry(gold.clone()).or_default() += 1;
            *fp.entry(pair.predicted.clone()).or_default() += 1;
        }
    }

    let classes: BTreeSet<_> = tp
        .keys()
        .chain(fp.keys())
        .chain(fn_count.keys())
        .cloned()
        .collect();
    let mut f1s = Vec::with_capacity(classes.len());
    let mut recall = BTreeMap::new();
    for class in classes {
        let t = *tp.get(&class).unwrap_or(&0) as f64;
        let f = *fp.get(&class).unwrap_or(&0) as f64;
        let n = *fn_count.get(&class).unwrap_or(&0) as f64;
        let precision = if t + f > 0.0 { t / (t + f) } else { 0.0 };
        let class_recall = if t + n > 0.0 { t / (t + n) } else { 0.0 };
        let f1 = if precision + class_recall > 0.0 {
            2.0 * precision * class_recall / (precision + class_recall)
        } else {
            0.0
        };
        f1s.push(f1);
        if t + n > 0.0 {
            recall.insert(class, rounded(class_recall));
        }
    }
    let macro_f1 = if f1s.is_empty() {
        0.0
    } else {
        f1s.iter().sum::<f64>() / f1s.len() as f64
    };
    serde_json::json!({
        "accuracy": if pairs.is_empty() { 0.0 } else { rounded(correct as f64 / pairs.len() as f64) },
        "macro_f1": rounded(macro_f1),
        "per_class_recall": recall,
        "n": pairs.len(),
    })
}

fn confusion(pairs: &[Pair]) -> serde_json::Value {
    let mut matrix = BTreeMap::<String, BTreeMap<String, usize>>::new();
    for pair in pairs {
        let gold = if pair.acceptable.contains(&pair.predicted) {
            &pair.predicted
        } else if let Some(first) = pair.acceptable.first() {
            first
        } else {
            continue;
        };
        *matrix
            .entry(gold.clone())
            .or_default()
            .entry(pair.predicted.clone())
            .or_default() += 1;
    }
    serde_json::to_value(matrix).expect("serializing metric maps cannot fail")
}

fn score_tools(pairs: &[(BTreeSet<String>, BTreeSet<String>)]) -> serde_json::Value {
    let (mut tp, mut fp, mut fn_count, mut exact) = (0usize, 0usize, 0usize, 0usize);
    for (gold, predicted) in pairs {
        tp += predicted.intersection(gold).count();
        fp += predicted.difference(gold).count();
        fn_count += gold.difference(predicted).count();
        exact += usize::from(gold == predicted);
    }
    let precision = if tp + fp == 0 {
        1.0
    } else {
        tp as f64 / (tp + fp) as f64
    };
    let recall = if tp + fn_count == 0 {
        1.0
    } else {
        tp as f64 / (tp + fn_count) as f64
    };
    let f1 = if precision + recall == 0.0 {
        0.0
    } else {
        2.0 * precision * recall / (precision + recall)
    };
    serde_json::json!({
        "precision": rounded(precision),
        "recall": rounded(recall),
        "f1": rounded(f1),
        "exact_set_accuracy": if pairs.is_empty() { 0.0 } else { rounded(exact as f64 / pairs.len() as f64) },
        "n": pairs.len(),
    })
}

/// Return the same report shape and aggregation semantics as Python's
/// `classification_metrics`, for already-produced classifier predictions.
pub fn classification_metrics(cases: &[MetricCase]) -> serde_json::Value {
    let mut single: BTreeMap<String, Vec<Pair>> = SINGLE_DIMS
        .iter()
        .map(|dim| ((*dim).to_owned(), Vec::new()))
        .collect();
    let mut tools_pairs = Vec::new();
    let mut failures = Vec::new();

    for case in cases {
        let mut failed = Vec::new();
        for dim in SINGLE_DIMS {
            let acceptable = case.expected.get(dim).cloned().unwrap_or_default();
            if acceptable.is_empty() {
                continue;
            }
            let predicted = case.predicted.get(dim).cloned().unwrap_or_default();
            single
                .get_mut(dim)
                .expect("all dimensions initialized")
                .push(Pair {
                    acceptable: acceptable.clone(),
                    predicted: predicted.clone(),
                });
            if !acceptable.contains(&predicted) {
                failed.push(serde_json::json!({ "dim": dim, "expected": acceptable, "predicted": predicted }));
            }
        }

        let expected_tools: BTreeSet<_> = case.expected_tools.iter().cloned().collect();
        let predicted_tools: BTreeSet<_> = case.predicted_tools.iter().cloned().collect();
        if !expected_tools.is_empty() || !predicted_tools.is_empty() {
            tools_pairs.push((expected_tools.clone(), predicted_tools.clone()));
            if expected_tools != predicted_tools {
                failed.push(serde_json::json!({
                    "dim": "tools",
                    "expected": expected_tools.into_iter().collect::<Vec<_>>(),
                    "predicted": predicted_tools.into_iter().collect::<Vec<_>>(),
                }));
            }
        }
        if !failed.is_empty() {
            failures.push(
                serde_json::json!({ "id": case.id, "prompt": case.prompt, "failed": failed }),
            );
        }
    }

    let mut report = serde_json::Map::new();
    for dim in SINGLE_DIMS {
        report.insert(
            dim.to_owned(),
            score_single(single.get(dim).expect("all dimensions initialized")),
        );
    }
    let risk = score_single(single.get("risk").expect("risk initialized"));
    let high_risk_recall = risk["per_class_recall"]
        .get("high")
        .cloned()
        .unwrap_or(serde_json::Value::Null);
    report.insert("tools".to_owned(), score_tools(&tools_pairs));
    report.insert(
        "confusion_task_type".to_owned(),
        confusion(single.get("task_type").expect("task_type initialized")),
    );
    report.insert(
        "confusion_risk".to_owned(),
        confusion(single.get("risk").expect("risk initialized")),
    );
    report.insert("high_risk_recall".to_owned(), high_risk_recall);
    report.insert("n_cases".to_owned(), serde_json::json!(cases.len()));
    report.insert("failures".to_owned(), serde_json::Value::Array(failures));
    serde_json::Value::Object(report)
}
