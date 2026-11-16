//! Rust evaluation runner for registered datasets and caller-supplied cases.
//!
//! The registered path owns collection, runtime discovery, grading, and
//! reproducibility provenance; explicit lower-level seams remain available for
//! deterministic contract tests and embedding.

use agentrouter_classifier::{classify, ClassifyOptions};
use agentrouter_core::Classification;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use crate::{
    classification_metrics, dataset_quality, evaluate_feedback, evaluate_platform,
    evaluate_provider, grade_classification, round_to, EvaluationCase, MetricCase, QualityCase,
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

fn metric_cases_with<F>(cases: &[EvaluationCase], classify_fn: &F) -> Vec<MetricCase>
where
    F: Fn(&str) -> Classification,
{
    cases
        .iter()
        .map(|case| {
            let prediction = classify_fn(&case.task);
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
}

fn bounded_command_output(program: &str, arguments: &[&str], cwd: &Path) -> Option<Vec<u8>> {
    let mut child = Command::new(program)
        .args(arguments)
        .current_dir(cwd)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .ok()?;
    let mut stdout = child.stdout.take()?;
    let reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        stdout.read_to_end(&mut bytes).ok().map(|_| bytes)
    });
    let deadline = Instant::now() + Duration::from_secs(5);
    let status = loop {
        match child.try_wait().ok()? {
            Some(status) => break status,
            None if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(10)),
            None => {
                let _ = child.kill();
                let _ = child.wait();
                let _ = reader.join();
                return None;
            }
        }
    };
    if !status.success() {
        let _ = reader.join();
        return None;
    }
    reader.join().ok()?
}

fn bounded_command_text(program: &str, arguments: &[&str], cwd: &Path) -> Option<String> {
    let output = String::from_utf8(bounded_command_output(program, arguments, cwd)?).ok()?;
    let output = output.trim().to_owned();
    (!output.is_empty()).then_some(output)
}

fn bounded_git_dirty(project_root: &Path) -> Option<bool> {
    bounded_command_output(
        "git",
        &["status", "--porcelain", "--untracked-files=normal"],
        project_root,
    )
    .map(|output| !output.is_empty())
}

/// Capture the Rust runner's reproducibility identity. This mirrors Python's
/// owned git/dirty/classifier identity fields while naming the actual runtime.
pub fn runtime_environment(project_root: &Path) -> serde_json::Value {
    let git_sha = bounded_command_text("git", &["rev-parse", "HEAD"], project_root);
    let git_dirty = bounded_git_dirty(project_root);
    let rustc = bounded_command_text("rustc", &["--version"], project_root);
    let classifier_sha256 = format!(
        "{:x}",
        Sha256::digest(include_bytes!("../../agentrouter-classifier/src/lib.rs"))
    );
    serde_json::json!({
        "agentrouter_version": agentrouter_core::package_version(),
        "runtime": "rust",
        "rustc": rustc,
        "platform": format!("{}-{}", std::env::consts::OS, std::env::consts::ARCH),
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "classifier_sha256": classifier_sha256,
    })
}

/// Collect registered local fixtures and run the Rust evaluation end to end.
/// Real data remains explicit: adapters without Rust real loaders produce
/// `SKIPPED_EXTERNAL` records and never fall back to their fixture files.
pub fn run_registered(options: RegisteredRunOptions) -> Result<serde_json::Value, String> {
    let selected_dataset = options.dataset.as_deref().filter(|value| !value.is_empty());
    let selected_profile = options.profile.as_deref().filter(|value| !value.is_empty());
    let names: Vec<String> = if let Some(dataset) = selected_dataset {
        crate::adapter_descriptor(dataset)?;
        vec![dataset.to_owned()]
    } else if let Some(profile) = selected_profile {
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
    if !matches!(options.source.as_str(), "fixture" | "real") {
        return Err(format!(
            "{}: unknown source '{}'",
            names.first().map(String::as_str).unwrap_or("dataset"),
            options.source
        ));
    }
    let name_refs = names.iter().map(String::as_str).collect::<Vec<_>>();
    // Python only enters the MASSIVE-specific filter path for a truthy language
    // list. An explicitly empty list therefore means the same as no filter.
    let massive_languages = if selected_dataset == Some("massive") {
        options
            .languages
            .as_deref()
            .filter(|languages| !languages.is_empty())
    } else {
        None
    };
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
    let environment = runtime_environment(&options.project_root);
    let run_options = RunOptions {
        // Dataset selection wins for collection, but Python still records the
        // caller's profile value in provenance when both are supplied.
        profile: options.profile,
        seed: options.seed,
        source: options.source,
        environment,
        datasets: collection.datasets,
        context_band_generalization,
    };
    if options.measure_all {
        // Python grades classification before entering the remaining
        // dimensions. Preserve that observable callback/error ordering before
        // runtime model and CLI discovery.
        let report = run_classification(
            &collection.cases,
            run_options.profile.as_deref(),
            run_options.seed,
            &run_options.source,
            run_options.environment.clone(),
            run_options.datasets.clone(),
            run_options.context_band_generalization.as_ref(),
        )?;
        let models = crate::evaluators_api::load_seed_models()?;
        let (commands, mut groups) = crate::evaluators_api::runtime_cli_surface()?;
        if !groups.iter().any(|group| group == "contract") {
            groups.push("contract".to_owned());
        }
        complete_all_dimensions_with(
            report,
            &collection.cases,
            &models,
            &commands,
            &groups,
            &|task| classify(task, &ClassifyOptions::default()),
        )
    } else {
        run_classification(
            &collection.cases,
            run_options.profile.as_deref(),
            run_options.seed,
            &run_options.source,
            run_options.environment,
            run_options.datasets,
            run_options.context_band_generalization.as_ref(),
        )
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
) -> Result<serde_json::Value, String> {
    run_classification_with(
        cases,
        profile,
        seed,
        source,
        environment,
        datasets,
        context_band_generalization,
        &|task| classify(task, &ClassifyOptions::default()),
    )
}

/// Run the public default Rust grading path. Model and CLI discovery are owned
/// by the runtime instead of being fabricated by callers.
pub fn run_default_grade(
    cases: &[EvaluationCase],
    measure_all: bool,
    context_band_generalization: Option<&serde_json::Value>,
) -> Result<serde_json::Value, String> {
    run_default_grade_with(cases, measure_all, context_band_generalization, &|task| {
        classify(task, &ClassifyOptions::default())
    })
}

/// Run the public grade contract with one caller-supplied classifier while
/// retaining automatic packaged-model and installed-CLI discovery.
pub fn run_default_grade_with<F>(
    cases: &[EvaluationCase],
    measure_all: bool,
    context_band_generalization: Option<&serde_json::Value>,
    classify_fn: &F,
) -> Result<serde_json::Value, String>
where
    F: Fn(&str) -> Classification,
{
    run_default_grade_with_loaders(
        cases,
        measure_all,
        context_band_generalization,
        classify_fn,
        crate::evaluators_api::load_seed_models,
        crate::evaluators_api::runtime_cli_surface,
    )
}

fn run_default_grade_with_loaders<F, ModelLoader, SurfaceLoader>(
    cases: &[EvaluationCase],
    measure_all: bool,
    context_band_generalization: Option<&serde_json::Value>,
    classify_fn: &F,
    model_loader: ModelLoader,
    surface_loader: SurfaceLoader,
) -> Result<serde_json::Value, String>
where
    F: Fn(&str) -> Classification,
    ModelLoader: FnOnce() -> Result<Vec<agentrouter_registry::ModelEntry>, String>,
    SurfaceLoader: FnOnce() -> Result<(Vec<String>, Vec<String>), String>,
{
    let options = RunOptions {
        profile: None,
        seed: 0,
        source: "runtime".to_owned(),
        environment: serde_json::Value::Null,
        datasets: serde_json::Value::Null,
        context_band_generalization: context_band_generalization.cloned(),
    };
    if !measure_all {
        let mut report = run_classification_with(
            cases,
            None,
            options.seed,
            &options.source,
            options.environment,
            options.datasets,
            options.context_band_generalization.as_ref(),
            classify_fn,
        )?;
        remove_runner_provenance(&mut report);
        return Ok(report);
    }
    let report = run_classification_with(
        cases,
        None,
        options.seed,
        &options.source,
        options.environment.clone(),
        options.datasets.clone(),
        options.context_band_generalization.as_ref(),
        classify_fn,
    )?;
    let models = model_loader()?;
    let (commands, mut groups) = surface_loader()?;
    // Python's Typer application registers `contract` as a hidden group. It is
    // intentionally absent from the Rust CLI's public help, but remains part of
    // the Python grading report contract mirrored by this default facade.
    if !groups.iter().any(|group| group == "contract") {
        groups.push("contract".to_owned());
    }
    let mut report =
        complete_all_dimensions_with(report, cases, &models, &commands, &groups, classify_fn)?;
    remove_runner_provenance(&mut report);
    Ok(report)
}

fn remove_runner_provenance(report: &mut serde_json::Value) {
    if let Some(object) = report.as_object_mut() {
        for field in [
            "environment",
            "datasets",
            "profile",
            "dataset_quality",
            "seed",
            "source",
        ] {
            object.remove(field);
        }
    }
}

/// Run classification grading through a caller-supplied classifier. The same
/// seam is used by the complete scorecard so one evaluation never mixes
/// predictions from different classifiers.
#[allow(clippy::too_many_arguments)]
pub fn run_classification_with<F>(
    cases: &[EvaluationCase],
    profile: Option<&str>,
    seed: i64,
    source: &str,
    environment: serde_json::Value,
    datasets: serde_json::Value,
    context_band_generalization: Option<&serde_json::Value>,
    classify_fn: &F,
) -> Result<serde_json::Value, String>
where
    F: Fn(&str) -> Classification,
{
    let metrics = classification_metrics(&metric_cases_with(cases, classify_fn));
    let mut report = grade_classification(&metrics, cases.len(), context_band_generalization)?;
    report["environment"] = environment;
    report["datasets"] = datasets;
    report["profile"] = profile.map_or(serde_json::Value::Null, |value| value.into());
    report["dataset_quality"] = dataset_quality(&quality_cases(cases));
    report["seed"] = seed.into();
    report["source"] = source.into();
    Ok(report)
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
    run_all_dimensions_with(cases, models, commands, groups, options, &|task| {
        classify(task, &ClassifyOptions::default())
    })
}

/// Run every measured dimension through one caller-supplied classifier.
/// Classification, routing, safety, and performance therefore describe the
/// same implementation, matching Python's `grade(..., classify_fn=...)` seam.
pub fn run_all_dimensions_with<F>(
    cases: &[EvaluationCase],
    models: &[agentrouter_registry::ModelEntry],
    commands: &[String],
    groups: &[String],
    options: RunOptions,
    classify_fn: &F,
) -> Result<serde_json::Value, String>
where
    F: Fn(&str) -> Classification,
{
    let report = run_classification_with(
        cases,
        options.profile.as_deref(),
        options.seed,
        &options.source,
        options.environment,
        options.datasets,
        options.context_band_generalization.as_ref(),
        classify_fn,
    )?;
    complete_all_dimensions_with(report, cases, models, commands, groups, classify_fn)
}

fn complete_all_dimensions_with<F>(
    mut report: serde_json::Value,
    cases: &[EvaluationCase],
    models: &[agentrouter_registry::ModelEntry],
    commands: &[String],
    groups: &[String],
    classify_fn: &F,
) -> Result<serde_json::Value, String>
where
    F: Fn(&str) -> Classification,
{
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
    let measured = [
        (
            "routing",
            crate::evaluate_routing_with(cases, models, classify_fn),
        ),
        ("safety", crate::evaluate_safety_with(cases, classify_fn)),
        ("cli_platform", evaluate_platform(commands, groups)),
        ("provider_registry", evaluate_provider(models)),
        (
            "feedback_storage",
            evaluate_feedback().map_err(|error| error.to_string())?,
        ),
        (
            "performance",
            crate::evaluate_performance_with(
                models,
                &crate::PERFORMANCE_SAMPLE_TASKS.map(str::to_owned),
                classify_fn,
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounded_runtime_commands_fail_closed_and_drain_large_output() {
        assert!(bounded_command_text(
            "agentrouter-command-that-does-not-exist",
            &[],
            Path::new(".")
        )
        .is_none());

        let directory = tempfile::tempdir().expect("temporary repository");
        if !Command::new("git")
            .arg("init")
            .current_dir(directory.path())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok_and(|status| status.success())
        {
            return;
        }
        for index in 0..3_000 {
            std::fs::write(
                directory
                    .path()
                    .join(format!("untracked-file-{index:04}.txt")),
                b"fixture",
            )
            .expect("write untracked fixture");
        }
        assert_eq!(bounded_git_dirty(directory.path()), Some(true));
        assert!(bounded_command_text(
            "git",
            &["config", "--get", "missing.agentrouter.key"],
            directory.path()
        )
        .is_none());
    }

    #[test]
    fn default_grade_propagates_packaged_model_load_failures() {
        let classified = std::cell::Cell::new(false);
        let case: EvaluationCase = serde_json::from_value(serde_json::json!({
            "id": "ordering",
            "dataset": "ordering",
            "task": "classify before discovery"
        }))
        .expect("valid ordering case");
        let result = run_default_grade_with_loaders(
            &[case],
            true,
            None,
            &|_| {
                classified.set(true);
                classify("classify before discovery", &ClassifyOptions::default())
            },
            || -> Result<Vec<agentrouter_registry::ModelEntry>, String> {
                assert!(
                    classified.get(),
                    "classification must precede model discovery"
                );
                Err("seed model catalog unavailable".to_owned())
            },
            || Ok((vec![], vec![])),
        );
        assert_eq!(result.unwrap_err(), "seed model catalog unavailable");
    }

    #[test]
    fn default_grade_propagates_cli_discovery_failures() {
        let classified = std::cell::Cell::new(false);
        let case: EvaluationCase = serde_json::from_value(serde_json::json!({
            "id": "ordering",
            "dataset": "ordering",
            "task": "classify before discovery"
        }))
        .expect("valid ordering case");
        let result = run_default_grade_with_loaders(
            &[case],
            true,
            None,
            &|_| {
                classified.set(true);
                classify("classify before discovery", &ClassifyOptions::default())
            },
            crate::evaluators_api::load_seed_models,
            || {
                assert!(
                    classified.get(),
                    "classification must precede CLI discovery"
                );
                Err("shipped CLI is unavailable".to_owned())
            },
        );
        assert_eq!(result.unwrap_err(), "shipped CLI is unavailable");
    }
}
