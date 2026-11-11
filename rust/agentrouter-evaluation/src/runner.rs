//! Offline Rust evaluation runner for caller-supplied normalized cases.
//!
//! Adapter construction and `measure_all` runtime discovery are still handled
//! by Python; this entry point runs the complete classification scorecard and
//! attaches deterministic dataset-quality and caller-supplied provenance.

use agentrouter_classifier::{classify, ClassifyOptions};
use std::path::PathBuf;

use crate::{
    classification_metrics, dataset_quality, evaluate_feedback, evaluate_performance,
    evaluate_platform, evaluate_provider, evaluate_routing, evaluate_safety, grade_classification,
    round_to, EvaluationCase, MetricCase, QualityCase,
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

#[derive(Debug, Clone)]
pub struct RunOptions {
    pub profile: Option<String>,
    pub seed: i64,
    pub source: String,
    pub environment: serde_json::Value,
    pub datasets: serde_json::Value,
    pub context_band_generalization: Option<serde_json::Value>,
}

#[derive(Debug, Clone)]
pub struct RegisteredRunOptions {
    pub project_root: PathBuf,
    pub dataset: Option<String>,
    pub profile: Option<String>,
    pub limit: Option<i64>,
    pub seed: i64,
    pub source: String,
    pub languages: Option<Vec<String>>,
    pub measure_all: bool,
    pub commands: Vec<String>,
    pub groups: Vec<String>,
    pub environment: serde_json::Value,
}

/// Collect registered local fixtures and run the Rust evaluation end to end.
/// Real data remains explicit: adapters without Rust real loaders produce
/// `SKIPPED_EXTERNAL` records and never fall back to their fixture files.
pub fn run_registered(options: RegisteredRunOptions) -> Result<serde_json::Value, String> {
    let names: Vec<String> = if let Some(dataset) = options.dataset.as_ref() {
        vec![dataset.clone()]
    } else if let Some(profile) = options.profile.as_deref() {
        crate::profile_datasets(profile)?
            .iter()
            .map(|name| (*name).to_owned())
            .collect()
    } else {
        crate::profile_datasets("fast")?
            .iter()
            .map(|name| (*name).to_owned())
            .collect()
    };
    let name_refs = names.iter().map(String::as_str).collect::<Vec<_>>();
    let massive_languages = (options.dataset.as_deref() == Some("massive"))
        .then_some(options.languages.as_deref())
        .flatten();
    let collection = crate::registry_api::collect(
        &name_refs,
        &options.project_root,
        options.limit,
        options.seed,
        &options.source,
        massive_languages,
    )?;
    let context_band_generalization = if options.measure_all {
        Some(crate::context_bands::evaluate_generalization()?)
    } else {
        None
    };
    let run_options = RunOptions {
        profile: if options.dataset.is_some() {
            None
        } else {
            options.profile
        },
        seed: options.seed,
        source: options.source,
        environment: options.environment,
        datasets: collection.datasets,
        context_band_generalization,
    };
    if options.measure_all {
        let models = crate::evaluators_api::load_seed_models()?;
        run_all_dimensions(
            &collection.cases,
            &models,
            &options.commands,
            &options.groups,
            run_options,
        )
    } else {
        Ok(run_classification(
            &collection.cases,
            run_options.profile.as_deref(),
            run_options.seed,
            &run_options.source,
            run_options.environment,
            run_options.datasets,
            run_options.context_band_generalization.as_ref(),
        ))
    }
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

/// Run the complete seven-dimension scorecard used by Python `grade(...,
/// measure_all=true)`. Inputs that depend on the caller's installed CLI or
/// registry are explicit, and feedback storage uses the crate's isolated
/// temporary database probe. Performance remains a local smoke measurement,
/// with the same eight task prompts and thresholds as Python.
pub fn run_all_dimensions(
    cases: &[EvaluationCase],
    models: &[agentrouter_registry::ModelEntry],
    commands: &[String],
    groups: &[String],
    options: RunOptions,
) -> Result<serde_json::Value, String> {
    use serde_json::{json, Value};

    const DIMENSIONS: [(&str, u64); 7] = [
        ("classification", 30),
        ("routing", 25),
        ("safety", 15),
        ("cli_platform", 10),
        ("provider_registry", 8),
        ("feedback_storage", 7),
        ("performance", 5),
    ];
    const PERFORMANCE_TASKS: [&str; 8] = [
        "Refactor the payment module and add unit tests",
        "Write a blog post about our API launch",
        "Summarize this 30k token incident report",
        "Design a scalable multi-tenant architecture",
        "Fix the off-by-one bug in the pagination helper",
        "Analyze the query plan and recommend indexes",
        "Rotate the production API keys and update secrets",
        "Draft release notes for version 2.1",
    ];

    let mut report = run_classification(
        cases,
        options.profile.as_deref(),
        options.seed,
        &options.source,
        options.environment,
        options.datasets,
        options.context_band_generalization.as_ref(),
    );
    let measured = [
        ("routing", evaluate_routing(cases, models)),
        ("safety", evaluate_safety(cases)),
        ("cli_platform", evaluate_platform(commands, groups)),
        ("provider_registry", evaluate_provider(models)),
        (
            "feedback_storage",
            evaluate_feedback().map_err(|error| error.to_string())?,
        ),
        (
            "performance",
            evaluate_performance(
                models,
                &PERFORMANCE_TASKS
                    .iter()
                    .map(|task| (*task).to_owned())
                    .collect::<Vec<_>>(),
            ),
        ),
    ];

    let mut dimensions = report["dimensions"]
        .as_object()
        .cloned()
        .ok_or_else(|| "classification grade has no dimensions object".to_owned())?;
    let class_points = report["dimensions"]["classification"]["achieved"]
        .as_f64()
        .unwrap_or(0.0);
    let mut achieved = 0.0;
    let mut gates = report["release_gates"]
        .as_object()
        .cloned()
        .ok_or_else(|| "classification grade has no release gates object".to_owned())?;
    for (name, result) in measured {
        let score = result["score"].as_f64().unwrap_or(0.0);
        let weight = DIMENSIONS
            .iter()
            .find(|(dimension, _)| *dimension == name)
            .map(|(_, weight)| *weight)
            .ok_or_else(|| format!("missing weight for evaluator {name}"))?;
        let points = round_to(weight as f64 * score, 3);
        achieved += points;
        dimensions.insert(
            name.to_owned(),
            json!({
                "weight": weight,
                "status": "measured",
                "score": round_to(score, 4),
                "achieved": points,
                "detail": result["detail"],
            }),
        );
        if name == "safety" {
            gates.insert("high_risk_gated==1.00".to_owned(), json!(score == 1.0));
        } else if name == "routing" {
            gates.insert(
                "synthetic_routing_top1>=0.95".to_owned(),
                json!(score >= 0.95),
            );
        }
    }
    achieved += class_points;
    let achieved = round_to(achieved, 2);
    let release_ready = gates.values().all(|gate| gate.as_bool() == Some(true));
    report["dimensions"] = Value::Object(dimensions);
    report["release_gates"] = Value::Object(std::mem::take(&mut gates));
    report["release_ready"] = json!(release_ready);
    report["achieved_points"] = json!(achieved);
    report["possible_measured_points"] = json!(100);
    report["grade_over_100"] = json!(achieved);
    report["grade_of_measured"] = json!(achieved);
    Ok(report)
}
