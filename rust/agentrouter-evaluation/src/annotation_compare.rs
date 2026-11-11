//! Rules/learned/hybrid context-band comparison mirrored from
//! `agentrouter.annotation.compare`.

use agentrouter_classifier::{classify, context_model, ClassifyOptions};
use agentrouter_core::ContextBand;
use serde::Serialize;
use serde_json::{json, Value};

use crate::annotation_packs::sample_indexes_python_seed;
use crate::annotation_schema::AdjudicatedItem;

pub const STRATEGIES: [&str; 3] = ["rules", "learned", "hybrid"];
pub const DEFAULT_HYBRID_THRESHOLD: f64 = 0.6;
const BOOTSTRAP_SAMPLES: usize = 2000;
const BOOTSTRAP_SEED: &str = "20260731";

#[derive(Debug, Clone, Copy)]
struct Prediction {
    band: ContextBand,
    confidence: f64,
    used_rules_fallback: bool,
}

fn predict(prompt: &str, strategy: &str, threshold: f64) -> Result<Prediction, String> {
    let rules_band = classify(prompt, &ClassifyOptions::default()).context_band;
    if strategy == "rules" {
        return Ok(Prediction {
            band: rules_band,
            confidence: 1.0,
            used_rules_fallback: true,
        });
    }
    let Some(model) = context_model::load_model() else {
        return Ok(Prediction {
            band: rules_band,
            confidence: 0.0,
            used_rules_fallback: true,
        });
    };
    let prediction = model.predict(prompt);
    let learned_band = match prediction.band.as_str() {
        "small" => ContextBand::Small,
        "medium" => ContextBand::Medium,
        "large" => ContextBand::Large,
        _ => {
            return Err(format!(
                "unknown learned context band {:?}",
                prediction.band
            ))
        }
    };
    match strategy {
        "learned" => Ok(Prediction {
            band: learned_band,
            confidence: prediction.confidence,
            used_rules_fallback: false,
        }),
        "hybrid" if prediction.confidence >= threshold => Ok(Prediction {
            band: learned_band,
            confidence: prediction.confidence,
            used_rules_fallback: false,
        }),
        "hybrid" => Ok(Prediction {
            band: rules_band,
            confidence: prediction.confidence,
            used_rules_fallback: true,
        }),
        _ => Err(format!("unknown strategy {strategy:?}")),
    }
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

fn macro_f1(gold: &[ContextBand], predicted: &[ContextBand]) -> f64 {
    [ContextBand::Small, ContextBand::Medium, ContextBand::Large]
        .iter()
        .map(|band| {
            let mut tp = 0;
            let mut fp = 0;
            let mut fn_ = 0;
            for (truth, guess) in gold.iter().zip(predicted) {
                if truth == band && guess == band {
                    tp += 1;
                } else if truth != band && guess == band {
                    fp += 1;
                } else if truth == band && guess != band {
                    fn_ += 1;
                }
            }
            let precision = if tp + fp == 0 {
                0.0
            } else {
                tp as f64 / (tp + fp) as f64
            };
            let recall = if tp + fn_ == 0 {
                0.0
            } else {
                tp as f64 / (tp + fn_) as f64
            };
            if precision + recall == 0.0 {
                0.0
            } else {
                2.0 * precision * recall / (precision + recall)
            }
        })
        .sum::<f64>()
        / 3.0
}

fn bootstrap_accuracy_ci(
    gold: &[ContextBand],
    predicted: &[ContextBand],
) -> Result<[f64; 2], String> {
    if gold.is_empty() {
        return Ok([0.0, 0.0]);
    }
    let indexes =
        sample_indexes_python_seed(gold.len(), BOOTSTRAP_SAMPLES * gold.len(), BOOTSTRAP_SEED)?;
    let mut accuracies = Vec::with_capacity(BOOTSTRAP_SAMPLES);
    for sample in indexes.chunks_exact(gold.len()) {
        let correct = sample
            .iter()
            .filter(|&&index| gold[index] == predicted[index])
            .count();
        accuracies.push(correct as f64 / gold.len() as f64);
    }
    accuracies.sort_by(f64::total_cmp);
    Ok([
        round4(accuracies[(0.025 * BOOTSTRAP_SAMPLES as f64) as usize]),
        round4(
            accuracies[((0.975 * BOOTSTRAP_SAMPLES as f64) as usize).min(BOOTSTRAP_SAMPLES - 1)],
        ),
    ])
}

fn ece(gold: &[ContextBand], predicted: &[ContextBand], confidences: &[f64]) -> f64 {
    if gold.is_empty() {
        return 0.0;
    }
    let mut buckets = vec![Vec::<usize>::new(); 10];
    for (index, confidence) in confidences.iter().enumerate() {
        let bucket = ((*confidence * 10.0) as usize).min(9);
        buckets[bucket].push(index);
    }
    let value = buckets
        .iter()
        .filter(|bucket| !bucket.is_empty())
        .map(|bucket| {
            let accuracy = bucket
                .iter()
                .filter(|&&index| gold[index] == predicted[index])
                .count() as f64
                / bucket.len() as f64;
            let mean_confidence =
                bucket.iter().map(|&index| confidences[index]).sum::<f64>() / bucket.len() as f64;
            bucket.len() as f64 / gold.len() as f64 * (accuracy - mean_confidence).abs()
        })
        .sum();
    round4(value)
}

#[derive(Debug, Serialize)]
pub struct StrategyReport {
    pub strategy: String,
    pub n: usize,
    pub accuracy: f64,
    pub macro_f1: f64,
    pub per_band_recall: Value,
    pub acc_ci95: [f64; 2],
    pub ece: f64,
    pub rules_fallback_rate: f64,
    pub abstained_items: usize,
}

pub fn evaluate(
    items: &[AdjudicatedItem],
    strategy: &str,
    threshold: f64,
) -> Result<StrategyReport, String> {
    let banded = items
        .iter()
        .filter(|item| !item.abstained && item.band.is_some())
        .collect::<Vec<_>>();
    let gold = banded
        .iter()
        .filter_map(|item| item.band)
        .collect::<Vec<_>>();
    let predictions = banded
        .iter()
        .map(|item| predict(&item.prompt, strategy, threshold))
        .collect::<Result<Vec<_>, _>>()?;
    let predicted = predictions
        .iter()
        .map(|prediction| prediction.band)
        .collect::<Vec<_>>();
    let confidences = predictions
        .iter()
        .map(|prediction| prediction.confidence)
        .collect::<Vec<_>>();
    let count = gold.len();
    let correct = gold
        .iter()
        .zip(&predicted)
        .filter(|(truth, guess)| truth == guess)
        .count();
    let mut recalls = serde_json::Map::new();
    for band in [ContextBand::Small, ContextBand::Medium, ContextBand::Large] {
        let support = gold.iter().filter(|&&truth| truth == band).count();
        let hits = gold
            .iter()
            .zip(&predicted)
            .filter(|(truth, guess)| **truth == band && **guess == band)
            .count();
        recalls.insert(
            band_name(band).to_owned(),
            if support == 0 {
                Value::Null
            } else {
                json!(round4(hits as f64 / support as f64))
            },
        );
    }
    let fallback_count = predictions
        .iter()
        .filter(|prediction| prediction.used_rules_fallback)
        .count();
    Ok(StrategyReport {
        strategy: strategy.to_owned(),
        n: count,
        accuracy: if count == 0 {
            0.0
        } else {
            round4(correct as f64 / count as f64)
        },
        macro_f1: round4(macro_f1(&gold, &predicted)),
        per_band_recall: Value::Object(recalls),
        acc_ci95: bootstrap_accuracy_ci(&gold, &predicted)?,
        ece: ece(&gold, &predicted, &confidences),
        rules_fallback_rate: if count == 0 {
            0.0
        } else {
            round4(fallback_count as f64 / count as f64)
        },
        abstained_items: items.iter().filter(|item| item.abstained).count(),
    })
}

pub fn compare_all(items: &[AdjudicatedItem], threshold: f64) -> Result<Value, String> {
    let mut reports = serde_json::Map::new();
    for strategy in STRATEGIES {
        reports.insert(
            strategy.to_owned(),
            serde_json::to_value(
                evaluate(items, strategy, threshold)
                    .map_err(|error| format!("{strategy}: {error}"))?,
            )
            .map_err(|error| error.to_string())?,
        );
    }
    Ok(Value::Object(reports))
}
