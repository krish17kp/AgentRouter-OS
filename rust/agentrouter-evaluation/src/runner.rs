//! Offline Rust evaluation runner for caller-supplied normalized cases.
//!
//! Adapter construction and `measure_all` runtime discovery are still handled
//! by Python; this entry point runs the complete classification scorecard and
//! attaches deterministic dataset-quality and caller-supplied provenance.

use agentrouter_classifier::{classify, ClassifyOptions};

use crate::{
    classification_metrics, dataset_quality, grade_classification, EvaluationCase, MetricCase,
    QualityCase,
};

fn strings<T: serde::Serialize>(values: &[T]) -> Vec<String> {
    values
        .iter()
        .filter_map(|value| {
            serde_json::to_value(value)
                .ok()?
                .as_str()
                .map(str::to_owned)
        })
        .collect()
}

fn enum_text<T: serde::Serialize>(value: &T) -> String {
    serde_json::to_value(value)
        .ok()
        .and_then(|value| value.as_str().map(str::to_owned))
        .unwrap_or_default()
}

fn metric_cases(cases: &[EvaluationCase]) -> Vec<MetricCase> {
    cases
        .iter()
        .map(|case| {
            let prediction = classify(&case.task, &ClassifyOptions::default());
            let expected = [
                ("task_type", strings(&case.expected.task_types)),
                ("complexity", strings(&case.expected.complexities)),
                ("risk", strings(&case.expected.risks)),
                ("output", strings(&case.expected.output_types)),
                ("context", strings(&case.expected.context_bands)),
                ("approval", strings(&case.expected.approval_levels)),
            ]
            .into_iter()
            .map(|(dimension, values)| (dimension.to_owned(), values))
            .collect();
            let predicted = [
                (
                    "task_type",
                    serde_json::to_value(prediction.task_type).unwrap(),
                ),
                (
                    "complexity",
                    serde_json::to_value(prediction.complexity).unwrap(),
                ),
                ("risk", serde_json::to_value(prediction.risk).unwrap()),
                (
                    "output",
                    serde_json::to_value(prediction.output_type).unwrap(),
                ),
                (
                    "context",
                    serde_json::to_value(prediction.context_band).unwrap(),
                ),
                (
                    "approval",
                    serde_json::to_value(prediction.approval_level).unwrap(),
                ),
            ]
            .into_iter()
            .map(|(dimension, value)| {
                (
                    dimension.to_owned(),
                    value.as_str().unwrap_or_default().to_owned(),
                )
            })
            .collect();
            MetricCase {
                id: case.id.clone(),
                prompt: case.task.clone(),
                expected,
                predicted,
                expected_tools: case.expected.required_tools.clone(),
                predicted_tools: prediction.tool_needs,
            }
        })
        .collect()
}

fn quality_cases(cases: &[EvaluationCase]) -> Vec<QualityCase> {
    cases
        .iter()
        .map(|case| QualityCase {
            task_hash: case.task_hash(),
            paraphrase_group: case.paraphrase_group.clone(),
            source_split: case.source_split.clone(),
            language: case.language.clone(),
            domain: case.domain.clone(),
            risk: case.expected.risks.first().map(enum_text),
            task_type: case.expected.task_types.first().map(enum_text),
            provenance_method: enum_text(&case.provenance.method),
        })
        .collect()
}

/// Run the Rust classifier and classification-only grade over normalized cases.
/// Runtime-dependent values are explicit inputs, keeping the report reproducible.
pub fn run_classification(
    cases: &[EvaluationCase],
    profile: Option<&str>,
    seed: i64,
    source: &str,
    environment: serde_json::Value,
    datasets: serde_json::Value,
    context_band_generalization: Option<&serde_json::Value>,
) -> serde_json::Value {
    let metrics = classification_metrics(&metric_cases(cases));
    let mut report = grade_classification(&metrics, cases.len(), context_band_generalization);
    report["environment"] = environment;
    report["datasets"] = datasets;
    report["profile"] = profile.map_or(serde_json::Value::Null, |value| value.into());
    report["dataset_quality"] = dataset_quality(&quality_cases(cases));
    report["seed"] = seed.into();
    report["source"] = source.into();
    report
}
