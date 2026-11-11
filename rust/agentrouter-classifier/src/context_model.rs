//! Contract-compatible port of `agentrouter/context_model.py`.
//!
//! The learned band model remains opt-in/off in the classifier, matching the
//! Python shipping default. This module exposes the exact deterministic
//! feature extraction and inference so training artifacts can be evaluated in
//! Rust without changing routing behavior.

use std::sync::OnceLock;

use regex::Regex;
use serde::{Deserialize, Serialize};

pub const FEATURES: [&str; 14] = [
    "explicit_ktoken",
    "explicit_tokens",
    "big_quantity",
    "definite_existing",
    "existing_marker",
    "review_verb",
    "pipeline",
    "conceptual",
    "new_indefinite",
    "big_corpus",
    "doc_noun",
    "self_contained",
    "wc_short",
    "wc_long",
];
pub const CLASSES: [&str; 3] = ["small", "medium", "large"];

const ARTIFACT: &str = r"(?:codebase|repo|repository|module|files?|project|system|subsystem|endpoints?|package|service|microservice|middleware|controller|handler|webhook|worker|parser|pipeline|scheduler|runner|library|client|lifecycle|flow|sequence|implementation|integration|migration|schema|configuration|deployment|dashboard|handbook|specification|document|codepath|tests?|suite|aggregates|traces?|partitions?)";
const PATTERNS: [&str; 12] = [
    r"(?i)(\d+)\s*k[\s-]*token",
    r"(?i)(\d{4,})\s*tokens?",
    r"(?i)(\d[\d,]{1,})\s*(page|file|document|record|partition|source file)",
    r"(?i)\b(?:the|its|this|these|those|our|their)\s+(?:\w+\s+){0,3}", /* ARTIFACT appended below */
    r"(?i)\b(existing|current|already|in use|used by|without changing|its\b|intermittent|cause of)",
    r"(?i)\b(review|audit|investigate|refactor|migrate|inspect|examine|diagnose|trace|assess|evaluate|modernize|harden|profile|reconcile|untangle|rework|maintainab)",
    r"(?i)\b(pipeline|etl|ingestion|warehouse|retrieval|vector d|data validation|data flow|aggregat|partition)",
    r"(?i)\b(explain|what makes|describe|outline|purpose of|define|workflow|useful\?)",
    r"(?i)\b(a|an)\s+(?:\w+\s+){0,2}(demo|sample|new|disposable|heading|snippet|prototype|scratch|toy|example)",
    r"(?i)\b(entire|whole|complete|monorepo|corpus|archive|dossier|acquisition|compliance|year of|thousands of|hundreds of)",
    r"(?i)\b(document|report|filing|book|transcript|pdf|dossier|archive|specification|spec|protocol)",
    r"(?i)\b(this sentence|these words|the following|below)",
];

fn regexes() -> &'static [Regex; 12] {
    static CELL: OnceLock<[Regex; 12]> = OnceLock::new();
    CELL.get_or_init(|| {
        PATTERNS
            .iter()
            .enumerate()
            .map(|(index, pattern)| {
                let pattern = if index == 3 {
                    format!("{pattern}{ARTIFACT}")
                } else {
                    (*pattern).to_string()
                };
                Regex::new(&pattern).expect("context feature regex is valid")
            })
            .collect::<Vec<_>>()
            .try_into()
            .expect("context feature regex count is fixed")
    })
}

pub fn feature_vector(prompt: &str) -> [f64; FEATURES.len()] {
    let patterns = regexes();
    let max_quantity = patterns[2]
        .captures_iter(prompt)
        .filter_map(|capture| capture.get(1))
        .filter_map(|value| value.as_str().replace(',', "").parse::<u64>().ok())
        .max()
        .unwrap_or(0);
    let word_count = prompt.split_whitespace().count();
    [
        f64::from(patterns[0].is_match(prompt)),
        f64::from(patterns[1].is_match(prompt)),
        f64::from(max_quantity >= 200),
        f64::from(patterns[3].is_match(prompt)),
        f64::from(patterns[4].is_match(prompt)),
        f64::from(patterns[5].is_match(prompt)),
        f64::from(patterns[6].is_match(prompt)),
        f64::from(patterns[7].is_match(prompt)),
        f64::from(patterns[8].is_match(prompt)),
        f64::from(patterns[9].is_match(prompt)),
        f64::from(patterns[10].is_match(prompt)),
        f64::from(patterns[11].is_match(prompt)),
        f64::from(word_count <= 6),
        f64::from(word_count >= 12),
    ]
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct LearnedBandModel {
    features: Vec<String>,
    classes: Vec<String>,
    coef: Vec<Vec<f64>>,
    intercept: Vec<f64>,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Prediction {
    pub band: String,
    pub confidence: f64,
}

impl LearnedBandModel {
    pub fn validate_json(raw: &str) -> Result<Self, String> {
        let model: Self =
            serde_json::from_str(raw).map_err(|_| "invalid model JSON".to_string())?;
        if model
            .features
            .iter()
            .map(String::as_str)
            .collect::<Vec<_>>()
            != FEATURES
        {
            return Err(
                "context-band model features do not match the code feature extractor".into(),
            );
        }
        if model.classes.iter().map(String::as_str).collect::<Vec<_>>() != CLASSES
            || model.coef.len() != CLASSES.len()
            || model.intercept.len() != CLASSES.len()
        {
            return Err("context-band model shape is invalid".into());
        }
        if model.coef.iter().any(|row| row.len() != FEATURES.len()) {
            return Err("context-band model coefficient width mismatch".into());
        }
        if model
            .coef
            .iter()
            .flatten()
            .chain(model.intercept.iter())
            .any(|value| !value.is_finite())
        {
            return Err("context-band model coefficients must be finite".into());
        }
        Ok(model)
    }

    pub fn predict(&self, prompt: &str) -> Prediction {
        let features = feature_vector(prompt);
        let logits: Vec<f64> = self
            .intercept
            .iter()
            .zip(&self.coef)
            .map(|(intercept, coefficients)| {
                intercept
                    + coefficients
                        .iter()
                        .zip(features)
                        .map(|(weight, value)| weight * value)
                        .sum::<f64>()
            })
            .collect();
        let max_logit = logits.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let exponentials: Vec<f64> = logits
            .iter()
            .map(|logit| (logit - max_logit).exp())
            .collect();
        let denominator: f64 = exponentials.iter().sum();
        let (best, confidence) = exponentials
            .iter()
            .enumerate()
            .map(|(index, value)| (index, value / denominator))
            .max_by(|left, right| left.1.total_cmp(&right.1))
            .expect("three classes are validated");
        Prediction {
            band: self.classes[best].clone(),
            confidence,
        }
    }
}

pub fn load_model() -> Option<&'static LearnedBandModel> {
    static CELL: OnceLock<Option<LearnedBandModel>> = OnceLock::new();
    CELL.get_or_init(|| {
        let raw = include_str!("../resources/context_band_model_v1.json");
        LearnedBandModel::validate_json(raw).ok()
    })
    .as_ref()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn artifact_loads_and_explicit_token_prompt_is_large() {
        let model = load_model().unwrap();
        let result = model.predict("Audit 120000 tokens of access-control traces.");
        assert_eq!(result.band, "large");
        assert!((0.0..=1.0).contains(&result.confidence));
    }

    #[test]
    fn mismatched_features_and_bad_shapes_are_rejected() {
        let mut value: serde_json::Value =
            serde_json::from_str(include_str!("../resources/context_band_model_v1.json")).unwrap();
        value["features"][0] = serde_json::Value::String("wrong".into());
        assert!(LearnedBandModel::validate_json(&value.to_string()).is_err());
        assert!(LearnedBandModel::validate_json("[]").is_err());
    }
}
