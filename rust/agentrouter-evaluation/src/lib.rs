//! Pure evaluation metric aggregation, ported from
//! `agentrouter/evaluation/metrics.py`.
//!
//! Predictions are supplied by the caller so the scorer can be differentially
//! checked offline without running a model or changing evaluation labels.

pub mod annotation_api;
pub mod annotation_candidates;
pub mod annotation_cli;
pub mod annotation_compare;
pub mod annotation_dedup;
pub mod annotation_graph_signals;
pub mod annotation_packs;
pub mod annotation_schema;
pub mod annotation_splits;
pub mod annotation_store;
pub mod context_bands;
pub mod evaluation_api;
pub mod evaluators_api;
pub mod legacy_gold;
pub mod package_markers;
pub mod registry_api;
pub mod runner;

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use agentrouter_core::{
    ApprovalLevel, Classification, ContextBand, Level, OutputType, PricingTier, TaskType,
};
use agentrouter_routing::round_half_even;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use unicode_general_category::{get_general_category, GeneralCategory};

pub const SINGLE_DIMS: [&str; 6] = [
    "task_type",
    "complexity",
    "risk",
    "output",
    "context",
    "approval",
];

pub const DATASET_NAMES: [&str; 8] = [
    "agentrouter-gold",
    "clinc150",
    "banking77",
    "massive",
    "longbench-v2",
    "swebench",
    "llmrouterbench",
    "twinrouterbench",
];

#[derive(Debug, Clone, Copy, Serialize)]
pub struct AdapterDescriptor {
    pub name: &'static str,
    pub module: &'static str,
    pub class: &'static str,
}

pub const ADAPTERS: [AdapterDescriptor; 8] = [
    AdapterDescriptor {
        name: "agentrouter-gold",
        module: "agentrouter_gold",
        class: "AgentRouterGoldAdapter",
    },
    AdapterDescriptor {
        name: "clinc150",
        module: "clinc150",
        class: "CLINC150Adapter",
    },
    AdapterDescriptor {
        name: "banking77",
        module: "banking77",
        class: "Banking77Adapter",
    },
    AdapterDescriptor {
        name: "massive",
        module: "massive",
        class: "MassiveAdapter",
    },
    AdapterDescriptor {
        name: "longbench-v2",
        module: "longbench_v2",
        class: "LongBenchV2Adapter",
    },
    AdapterDescriptor {
        name: "swebench",
        module: "swebench",
        class: "SWEBenchAdapter",
    },
    AdapterDescriptor {
        name: "llmrouterbench",
        module: "llmrouterbench",
        class: "LLMRouterBenchAdapter",
    },
    AdapterDescriptor {
        name: "twinrouterbench",
        module: "twinrouterbench",
        class: "TwinRouterBenchAdapter",
    },
];

pub const PROFILE_NAMES: [&str; 5] = ["fast", "pr", "nightly", "release", "full"];
/// Stable default task set used by Python's performance smoke evaluator.
pub const PERFORMANCE_SAMPLE_TASKS: [&str; 8] = [
    "Refactor the payment module and add unit tests",
    "Write a blog post about our API launch",
    "Summarize this 30k token incident report",
    "Design a scalable multi-tenant architecture",
    "Fix the off-by-one bug in the pagination helper",
    "Analyze the query plan and recommend indexes",
    "Rotate the production API keys and update secrets",
    "Draft release notes for version 2.1",
];

const GRADE_DIMENSIONS: [(&str, u64); 7] = [
    ("classification", 30),
    ("routing", 25),
    ("safety", 15),
    ("cli_platform", 10),
    ("provider_registry", 8),
    ("feedback_storage", 7),
    ("performance", 5),
];
const CLASSIFICATION_SUBWEIGHTS: [(&str, u64); 7] = [
    ("task_type", 10),
    ("risk", 7),
    ("complexity", 4),
    ("tools", 4),
    ("output", 2),
    ("context", 2),
    ("approval", 1),
];

/// Build the scorecard and classification-only release gates produced by
/// Python `evaluation.grading.grade` when `measure_all` is false.
pub fn grade_classification(
    metrics: &serde_json::Value,
    n_cases: usize,
    context_band_generalization: Option<&serde_json::Value>,
) -> serde_json::Value {
    use serde_json::{json, Map, Value};

    let mut detail = Map::new();
    let mut weighted_score = 0.0;
    for (dimension, weight) in CLASSIFICATION_SUBWEIGHTS {
        let score = if dimension == "tools" {
            metrics["tools"]["f1"].as_f64().unwrap_or(0.0)
        } else {
            metrics[dimension]["accuracy"].as_f64().unwrap_or(0.0)
        };
        detail.insert(
            dimension.to_owned(),
            json!({"weight": weight, "score": score}),
        );
        weighted_score += weight as f64 * score;
    }
    let raw_class_score = weighted_score / 30.0;
    let class_score = round_to(raw_class_score, 4);

    let mut dimensions = Map::new();
    for (dimension, weight) in GRADE_DIMENSIONS {
        let entry = if dimension == "classification" {
            json!({
                "weight": weight,
                "status": "measured",
                "score": class_score,
                "achieved": round_to(weight as f64 * raw_class_score, 3),
                "detail": detail.clone(),
            })
        } else {
            json!({"weight": weight, "status": "pending", "score": null, "achieved": 0.0})
        };
        dimensions.insert(dimension.to_owned(), entry);
    }

    let achieved: f64 = dimensions
        .values()
        .map(|dimension| dimension["achieved"].as_f64().unwrap_or(0.0))
        .sum();
    let context_accuracy = context_band_generalization
        .and_then(|value| value.get("current_holdout"))
        .and_then(|value| value.get("accuracy"))
        .and_then(Value::as_f64)
        .unwrap_or_else(|| metrics["context"]["accuracy"].as_f64().unwrap_or(0.0));
    let gates = json!({
        "task_type_macro_f1>=0.90": metrics["task_type"]["macro_f1"].as_f64().unwrap_or(0.0) >= 0.90,
        "high_risk_recall==1.00": metrics["high_risk_recall"].as_f64() == Some(1.0),
        "approval_accuracy==1.00": metrics["approval"]["accuracy"].as_f64() == Some(1.0),
        "tool_needs_f1>=0.90": metrics["tools"]["f1"].as_f64().unwrap_or(0.0) >= 0.90,
        "context_band_accuracy>=0.90": context_accuracy >= 0.90,
    });

    let mut result = json!({
        "n_cases": n_cases,
        "dimensions": dimensions,
        "achieved_points": round_to(achieved, 2),
        "possible_measured_points": 30,
        "grade_over_100": round_to(achieved, 2),
        "grade_of_measured": round_to(100.0 * achieved / 30.0, 2),
        "classification": metrics,
        "release_gates": gates,
        "release_ready": gates
            .as_object()
            .is_some_and(|gates| gates.values().all(|value| value.as_bool() == Some(true))),
    });
    if let Some(generalization) = context_band_generalization {
        result["context_band_generalization"] = generalization.clone();
    }
    result
}

/// Run the safety evaluator from `evaluation.evaluators.safety` against the
/// Rust classifier. A missing gold safety label remains explicitly marked as
/// a proxy measurement, matching the Python evaluator's release reporting.
pub fn evaluate_safety(cases: &[EvaluationCase]) -> serde_json::Value {
    use agentrouter_classifier::{classify, ClassifyOptions};
    evaluate_safety_with(cases, |task| classify(task, &ClassifyOptions::default()))
}

/// Evaluate safety while using a caller-provided classifier, matching Python's
/// optional `classify_fn` seam for deterministic offline evaluation.
pub fn evaluate_safety_with<F>(cases: &[EvaluationCase], classify_fn: F) -> serde_json::Value
where
    F: Fn(&str) -> Classification,
{
    use serde_json::{json, Value};

    let mut high_risk_total = 0usize;
    let mut recalled = 0usize;
    let mut gated = 0usize;
    let mut used_proxy = false;
    let mut failures = Vec::new();

    for case in cases {
        let prediction = classify_fn(&case.task);
        let gold = if case
            .safety
            .as_ref()
            .is_some_and(|safety| safety.must_require_human_approval)
        {
            Some(true)
        } else if !case.expected.risks.is_empty() {
            Some(case.expected.risks.iter().all(|risk| *risk == Level::High))
        } else {
            None
        };
        if gold.is_none() {
            used_proxy = true;
        }
        let is_high = gold.unwrap_or(prediction.risk == Level::High);
        if !is_high {
            continue;
        }

        high_risk_total += 1;
        let flagged = prediction.risk == Level::High;
        let auto_execute_allowed =
            prediction.risk != Level::High && prediction.approval_level == ApprovalLevel::Auto;
        let blocked = !auto_execute_allowed;
        let human = prediction.approval_level == ApprovalLevel::HumanApprovalRequired;
        if flagged {
            recalled += 1;
        }
        if flagged && blocked && human {
            gated += 1;
        } else {
            failures.push(json!({
                "id": case.id,
                "predicted_risk": prediction.risk,
                "auto_execute_allowed": auto_execute_allowed,
                "approval_level": prediction.approval_level,
            }));
        }
    }

    let score = if high_risk_total == 0 {
        1.0
    } else {
        gated as f64 / high_risk_total as f64
    };
    let recall: Option<f64> =
        (high_risk_total > 0).then(|| round_to(recalled as f64 / high_risk_total as f64, 4));
    json!({
        "score": round_to(score, 4),
        "detail": {
            "high_risk_cases": high_risk_total,
            "correctly_gated": gated,
            "high_risk_recall": recall,
            "measurement": if used_proxy { "proxy" } else { "gold" },
            "note": "gate = classifier risk==high AND approval==human-approval-required AND auto_execute blocked",
            "failures": failures.into_iter().take(20).collect::<Vec<Value>>(),
        }
    })
}

/// Validate provider metadata using the exact field checklist from
/// `evaluation.evaluators.provider.evaluate_provider`.
pub fn evaluate_provider(models: &[agentrouter_registry::ModelEntry]) -> serde_json::Value {
    use serde_json::json;

    const PLACEHOLDERS: [&str; 7] = ["", "unknown", "tbd", "todo", "placeholder", "n/a", "none"];
    const FIELDS: [&str; 6] = [
        "vendor",
        "model_id",
        "release_channel",
        "context_window",
        "provenance.source",
        "provenance.last_updated",
    ];

    let clean = |value: &str| !PLACEHOLDERS.contains(&value.trim().to_lowercase().as_str());
    let mut failures = Vec::new();
    for model in models {
        let mut missing = Vec::new();
        if !clean(model.vendor()) {
            missing.push("vendor");
        }
        if !clean(&model.model_id) {
            missing.push("model_id");
        }
        let release_channel = serde_json::to_value(model.release_channel)
            .unwrap_or_default()
            .as_str()
            .unwrap_or_default()
            .to_owned();
        if !clean(&release_channel) {
            missing.push("release_channel");
        }
        if !agentrouter_core::pydantic_integer_is_positive(&model.context_window) {
            missing.push("context_window");
        }
        if model.source.as_deref().is_none_or(|source| !clean(source)) {
            missing.push("provenance.source");
        }
        if model.last_updated.is_none() {
            missing.push("provenance.last_updated");
        }
        if !missing.is_empty() {
            failures.push(json!({"model": model.key(), "missing": missing}));
        }
    }
    let passed = models.len() - failures.len();
    json!({
        "score": if models.is_empty() { 0.0 } else { round_to(passed as f64 / models.len() as f64, 4) },
        "detail": {
            "n_models": models.len(),
            "passed": passed,
            "fields_checked": FIELDS,
            "failures": failures,
        }
    })
}

/// Evaluate the packaged seed registry, matching Python's no-argument
/// `evaluate_provider()` call.
pub fn evaluate_provider_default() -> Result<serde_json::Value, String> {
    let models = evaluators_api::load_seed_models()?;
    Ok(evaluate_provider(&models))
}

/// Exercise the decision + feedback SQLite round-trip from
/// `evaluation.evaluators.feedback` using an isolated temporary home.
pub fn evaluate_feedback() -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    use serde_json::{json, Map, Value};
    use std::time::{SystemTime, UNIX_EPOCH};

    let nonce = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
    let home = std::env::temp_dir().join(format!(
        "agentrouter-eval-feedback-{}-{nonce}",
        std::process::id()
    ));
    std::fs::create_dir_all(&home)?;

    let checks = (|| -> Result<Map<String, Value>, Box<dyn std::error::Error>> {
        let conn = agentrouter_storage::connect(&home)?;
        let payload = json!({
            "classification": {"risk": "high"},
            "recommendation": {"model": "anthropic/claude-opus-4-8", "score": 0.87},
        });
        let decision_id =
            agentrouter_storage::save_decision(&conn, "deploy to production", &payload)?;
        let loaded = agentrouter_storage::load_decision(&conn, &decision_id)?;
        let mut checks = Map::new();
        checks.insert(
            "decision_saved".to_owned(),
            json!(decision_id.starts_with("d_")),
        );
        checks.insert("decision_loaded".to_owned(), json!(loaded.is_some()));
        checks.insert(
            "task_roundtrip".to_owned(),
            json!(
                loaded
                    .as_ref()
                    .and_then(|value| value.get("task"))
                    .and_then(Value::as_str)
                    == Some("deploy to production")
            ),
        );
        checks.insert(
            "recommendation_roundtrip".to_owned(),
            json!(
                loaded
                    .as_ref()
                    .and_then(|value| value.pointer("/recommendation/model"))
                    .and_then(Value::as_str)
                    == Some("anthropic/claude-opus-4-8")
            ),
        );
        let recorded = agentrouter_storage::record_feedback(&conn, &decision_id, 5, "great")?;
        let stats = agentrouter_storage::aggregate_stats(&conn, None)?;
        checks.insert(
            "stats_decision_count".to_owned(),
            json!(stats["decisions"] == 1),
        );
        checks.insert(
            "stats_by_risk".to_owned(),
            json!(stats["by_risk"]["high"] == 1),
        );
        checks.insert(
            "stats_feedback_count".to_owned(),
            json!(recorded && stats["feedback"]["count"] == 1),
        );
        drop(conn);
        Ok(checks)
    })();

    let _ = std::fs::remove_dir_all(&home);
    let checks = checks?;
    let score = if checks.values().all(|check| check.as_bool() == Some(true)) {
        1.0
    } else {
        0.0
    };
    Ok(json!({"score": score, "detail": {"checks": checks}}))
}

/// Score router top-1 results against gold constraints or the declared
/// recommendation/distinct-fallback proxy from `evaluation.evaluators.routing`.
pub fn evaluate_routing(
    cases: &[EvaluationCase],
    models: &[agentrouter_registry::ModelEntry],
) -> serde_json::Value {
    use agentrouter_classifier::{classify, ClassifyOptions};
    evaluate_routing_with(cases, models, |task| {
        classify(task, &ClassifyOptions::default())
    })
}

/// Evaluate routing with a caller-provided classifier, matching Python's
/// optional `classify_fn` argument.
pub fn evaluate_routing_with<F>(
    cases: &[EvaluationCase],
    models: &[agentrouter_registry::ModelEntry],
    classify_fn: F,
) -> serde_json::Value
where
    F: Fn(&str) -> Classification,
{
    use agentrouter_routing::{route, Weights};
    use serde_json::{json, Value};

    let mut gold_count = 0usize;
    let mut proxy_count = 0usize;
    let mut passed = 0usize;
    let mut with_recommendation = 0usize;
    let mut failures = Vec::new();

    for case in cases {
        let classification = classify_fn(&case.task);
        let result = route(models, &classification, Weights::default(), None);
        let recommendation = result.recommendation.map(|row| row.model);
        let fallback = result.fallback.map(|row| row.model);
        if recommendation.is_some() {
            with_recommendation += 1;
        }

        let (ok, reason) = if let Some(expectation) = &case.routing {
            gold_count += 1;
            match recommendation.as_deref() {
                None => (false, Some("no recommendation".to_owned())),
                Some(key) => {
                    // Python builds `by_key` with a dict comprehension, so the
                    // last duplicate key supplies the constraint metadata.
                    let model = models.iter().rev().find(|model| model.key() == key);
                    let Some(model) = model else {
                        failures.push(json!({
                            "id": case.id,
                            "reason": "recommendation missing from registry",
                            "recommendation": key,
                        }));
                        continue;
                    };
                    routing_constraints(model, expectation)
                }
            }
        } else {
            proxy_count += 1;
            let sane = recommendation.is_some() && fallback.is_some() && recommendation != fallback;
            (
                sane,
                (!sane).then(|| "recommendation missing or fallback not distinct".to_owned()),
            )
        };

        if ok {
            passed += 1;
        } else {
            failures.push(json!({
                "id": case.id,
                "reason": reason,
                "recommendation": recommendation,
            }));
        }
    }

    let count = cases.len();
    let score = if count == 0 {
        0.0
    } else {
        round_to(passed as f64 / count as f64, 4)
    };
    let coverage = if count == 0 {
        0.0
    } else {
        round_to(with_recommendation as f64 / count as f64, 4)
    };
    let measurement = if gold_count > 0 && proxy_count == 0 {
        "gold"
    } else if gold_count == 0 {
        "proxy"
    } else {
        "mixed"
    };
    json!({
        "score": score,
        "detail": {
            "n_cases": count,
            "n_gold": gold_count,
            "n_proxy": proxy_count,
            "measurement": measurement,
            "top1": score,
            "recommendation_coverage": coverage,
            "proxy_note": "proxy cases scored on: recommendation non-None AND distinct fallback; NOT verified against a gold routing target",
            "failures": failures.into_iter().take(20).collect::<Vec<Value>>(),
        }
    })
}

/// Score the command/group manifest using the CLI platform evaluator's fixed
/// user-facing surface. Discovery of registered commands is supplied by the
/// runtime adapter, just as Typer performs it in Python.
pub fn evaluate_platform(commands: &[String], groups: &[String]) -> serde_json::Value {
    use serde_json::json;
    use std::collections::BTreeSet;

    const EXPECTED_COMMANDS: [&str; 9] = [
        "init",
        "setup",
        "route",
        "explain",
        "feedback",
        "execute",
        "stats",
        "dashboard",
        "evaluate",
    ];
    const EXPECTED_GROUPS: [&str; 7] = [
        "registry",
        "providers",
        "prompt",
        "hosts",
        "models",
        "plugin",
        "eval",
    ];
    let commands_found: BTreeSet<_> = commands.iter().map(String::as_str).collect();
    let groups_found: BTreeSet<_> = groups.iter().map(String::as_str).collect();
    let expected: BTreeSet<_> = EXPECTED_COMMANDS
        .into_iter()
        .chain(EXPECTED_GROUPS)
        .collect();
    let present = expected
        .iter()
        .filter(|name| commands_found.contains(**name) || groups_found.contains(**name))
        .count();
    let missing: Vec<_> = expected
        .iter()
        .filter(|name| !commands_found.contains(**name) && !groups_found.contains(**name))
        .copied()
        .collect();
    let score = if expected.is_empty() {
        0.0
    } else {
        round_to(present as f64 / expected.len() as f64, 4)
    };
    json!({
        "score": score,
        "detail": {
            "expected": expected.len(),
            "present": present,
            "missing": missing,
            "commands_found": commands_found,
            "groups_found": groups_found,
        }
    })
}

/// Summarize elapsed seconds using the performance evaluator's stable scoring
/// contract. Measuring classify/route timings remains the runtime adapter's
/// responsibility because results are machine-dependent.
pub fn summarize_performance(classify_seconds: &[f64], route_seconds: &[f64]) -> serde_json::Value {
    use serde_json::json;

    const CLASSIFY_THRESHOLD_MS: f64 = 50.0;
    const ROUTE_THRESHOLD_MS: f64 = 100.0;
    let classify_median_ms = median_milliseconds(classify_seconds);
    let route_median_ms = median_milliseconds(route_seconds);
    let score = degrade(classify_median_ms, CLASSIFY_THRESHOLD_MS)
        .min(degrade(route_median_ms, ROUTE_THRESHOLD_MS));
    json!({
        "score": round_to(score, 4),
        "detail": {
            "n_samples": classify_seconds.len(),
            "classify_median_ms": classify_median_ms,
            "route_median_ms": route_median_ms,
            "classify_threshold_ms": CLASSIFY_THRESHOLD_MS,
            "route_threshold_ms": ROUTE_THRESHOLD_MS,
            "note": "smoke perf check on this machine; not a benchmark",
        }
    })
}

/// Measure the default Rust classifier and router over caller-supplied cases.
/// Callers supply the model catalog and task list; seed loading remains in the
/// packaging/runtime adapter.
pub fn evaluate_performance(
    models: &[agentrouter_registry::ModelEntry],
    tasks: &[String],
) -> serde_json::Value {
    evaluate_performance_with(models, tasks, |task| {
        agentrouter_classifier::classify(task, &agentrouter_classifier::ClassifyOptions::default())
    })
}

/// Measure the default classifier and router against Python's default
/// performance task set and embedded seed registry.
pub fn evaluate_default_performance() -> Result<serde_json::Value, String> {
    let models = evaluators_api::load_seed_models()?;
    let tasks = PERFORMANCE_SAMPLE_TASKS
        .iter()
        .map(|task| (*task).to_owned())
        .collect::<Vec<_>>();
    Ok(evaluate_performance(&models, &tasks))
}

/// Measure routing latency using a caller-supplied classifier, matching
/// Python's injectable `classify_fn` seam for deterministic and specialized
/// evaluation runs.
pub fn evaluate_performance_with<F>(
    models: &[agentrouter_registry::ModelEntry],
    tasks: &[String],
    classify_fn: F,
) -> serde_json::Value
where
    F: Fn(&str) -> agentrouter_core::Classification,
{
    use std::time::Instant;

    let mut classify_seconds = Vec::with_capacity(tasks.len());
    let mut route_seconds = Vec::with_capacity(tasks.len());
    for task in tasks {
        let classify_start = Instant::now();
        let classification = classify_fn(task);
        let route_start = Instant::now();
        let _route = std::hint::black_box(agentrouter_routing::route(
            models,
            &classification,
            agentrouter_routing::Weights::default(),
            None,
        ));
        let route_end = Instant::now();
        classify_seconds.push(route_start.duration_since(classify_start).as_secs_f64());
        route_seconds.push(route_end.duration_since(route_start).as_secs_f64());
    }
    summarize_performance(&classify_seconds, &route_seconds)
}

/// Compare two completed evaluation reports using the Python release
/// regression contract.
pub fn compare_results(
    baseline: &serde_json::Value,
    current: &serde_json::Value,
) -> serde_json::Value {
    use serde_json::{json, Map, Value};

    const REGRESSION_EPSILON: f64 = 1e-4;
    let scores = |result: &Value| -> BTreeMap<String, f64> {
        result
            .get("dimensions")
            .and_then(Value::as_object)
            .into_iter()
            .flat_map(|dimensions| dimensions.iter())
            .filter_map(|(name, dimension)| {
                dimension
                    .get("score")
                    .and_then(Value::as_f64)
                    .map(|score| (name.clone(), score))
            })
            .collect()
    };
    let baseline_scores = scores(baseline);
    let current_scores = scores(current);
    let mut regressions = Vec::new();
    let mut improvements = Vec::new();
    for (dimension, baseline_score) in &baseline_scores {
        let Some(current_score) = current_scores.get(dimension) else {
            continue;
        };
        let delta = round_to(current_score - baseline_score, 6);
        let row = json!({
            "dimension": dimension,
            "baseline": baseline_score,
            "current": current_score,
            "delta": delta,
        });
        if delta < -REGRESSION_EPSILON {
            regressions.push(row);
        } else if delta > REGRESSION_EPSILON {
            improvements.push(row);
        }
    }

    let baseline_gates = baseline
        .get("release_gates")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_else(Map::new);
    let current_gates = current
        .get("release_gates")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_else(Map::new);
    let gate_regressions: Vec<_> = current_gates
        .iter()
        .filter(|(gate, status)| {
            baseline_gates.get(*gate).and_then(Value::as_bool) == Some(true)
                && status.as_bool() == Some(false)
        })
        .map(|(gate, _)| gate.clone())
        .collect();
    let baseline_grade = baseline
        .get("grade_over_100")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    let current_grade = current
        .get("grade_over_100")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    json!({
        "regressions": regressions,
        "improvements": improvements,
        "gate_regressions": gate_regressions,
        "grade_delta": round_to(current_grade - baseline_grade, 2),
        "has_critical_regression": !regressions.is_empty() || !gate_regressions.is_empty(),
    })
}

/// Load a previously written evaluation report from UTF-8 JSON.
pub fn load_result(
    path: &std::path::Path,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let contents = std::fs::read_to_string(path)?;
    Ok(serde_json::from_str(&contents)?)
}

/// Render the stable comparison Markdown and CSV artifacts.
pub fn write_comparison(
    comparison: &serde_json::Value,
    out_dir: &std::path::Path,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    use std::fs;

    fs::create_dir_all(out_dir)?;
    let mut lines = vec![
        "# Baseline vs current".to_owned(),
        String::new(),
        format!(
            "- grade delta: {}",
            python_string(
                comparison
                    .get("grade_delta")
                    .unwrap_or(&serde_json::Value::Null)
            )
        ),
        format!(
            "- critical regression: {}",
            if comparison
                .get("has_critical_regression")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(false)
            {
                "YES"
            } else {
                "NO"
            }
        ),
        format!(
            "- gate regressions: {}",
            python_list(
                comparison
                    .get("gate_regressions")
                    .and_then(serde_json::Value::as_array)
            )
        ),
        String::new(),
        "## Regressions".to_owned(),
        String::new(),
    ];
    append_comparison_rows(&mut lines, comparison.get("regressions"));
    lines.extend([String::new(), "## Improvements".to_owned(), String::new()]);
    append_comparison_rows(&mut lines, comparison.get("improvements"));
    fs::write(
        out_dir.join("comparison.md"),
        format!("{}\n", lines.join("\n")),
    )?;

    let mut written = vec!["comparison.md".to_owned()];
    for (filename, key) in [
        ("regressions.csv", "regressions"),
        ("improvements.csv", "improvements"),
    ] {
        let mut csv = vec![csv_record(&[
            "dimension".to_owned(),
            "baseline".to_owned(),
            "current".to_owned(),
            "delta".to_owned(),
        ])];
        if let Some(rows) = comparison.get(key).and_then(serde_json::Value::as_array) {
            for row in rows {
                csv.push(csv_record(&[
                    result_value(row, "dimension"),
                    result_value(row, "baseline"),
                    result_value(row, "current"),
                    result_value(row, "delta"),
                ]));
            }
        }
        fs::write(out_dir.join(filename), csv.concat())?;
        written.push(filename.to_owned());
    }
    Ok(written)
}

fn append_comparison_rows(lines: &mut Vec<String>, rows: Option<&serde_json::Value>) {
    if let Some(rows) = rows.and_then(serde_json::Value::as_array) {
        for row in rows {
            let dimension = result_value(row, "dimension");
            let baseline = result_value(row, "baseline");
            let current = result_value(row, "current");
            let delta = row
                .get("delta")
                .and_then(serde_json::Value::as_f64)
                .unwrap_or_default();
            lines.push(format!(
                "- {dimension}: {baseline} -> {current} ({delta:+})"
            ));
        }
    }
}

fn python_list(values: Option<&Vec<serde_json::Value>>) -> String {
    let Some(values) = values.filter(|values| !values.is_empty()) else {
        return "none".to_owned();
    };
    format!(
        "[{}]",
        values
            .iter()
            .map(|value| {
                let value = python_string(value);
                let quote = if value.contains('\'') && !value.contains('"') {
                    '"'
                } else {
                    '\''
                };
                let escaped = value
                    .replace('\\', "\\\\")
                    .replace(quote, &format!("\\{quote}"));
                format!("{quote}{escaped}{quote}")
            })
            .collect::<Vec<_>>()
            .join(", ")
    )
}

fn median_milliseconds(samples_seconds: &[f64]) -> f64 {
    if samples_seconds.is_empty() {
        return 0.0;
    }
    let mut ordered = samples_seconds.to_vec();
    ordered.sort_by(f64::total_cmp);
    let median = if ordered.len().is_multiple_of(2) {
        (ordered[ordered.len() / 2 - 1] + ordered[ordered.len() / 2]) / 2.0
    } else {
        ordered[ordered.len() / 2]
    };
    round_to(median * 1000.0, 3)
}

fn degrade(median_ms: f64, threshold_ms: f64) -> f64 {
    if median_ms <= threshold_ms {
        1.0
    } else {
        (1.0 - (median_ms - threshold_ms) / threshold_ms).max(0.0)
    }
}

fn routing_constraints(
    model: &agentrouter_registry::ModelEntry,
    expectation: &RoutingExpectation,
) -> (bool, Option<String>) {
    use serde_json::Value;

    for (dimension, floor) in &expectation.minimum_ability {
        let ability = match dimension.as_str() {
            "coding" => model.ability.coding,
            "reasoning" => model.ability.reasoning,
            "writing" => model.ability.writing,
            _ => 0,
        };
        if i64::from(ability) < *floor {
            return (
                false,
                Some(format!("ability.{dimension} {ability} < {floor}")),
            );
        }
    }
    if !expectation.acceptable_pricing_tiers.is_empty()
        && !expectation
            .acceptable_pricing_tiers
            .contains(&model.pricing_tier)
    {
        let tier = serde_json::to_value(model.pricing_tier)
            .unwrap_or(Value::Null)
            .as_str()
            .unwrap_or_default()
            .to_owned();
        return (false, Some(format!("pricing_tier {tier} not acceptable")));
    }
    if !expectation.permitted_providers.is_empty()
        && !expectation.permitted_providers.contains(&model.provider)
    {
        return (
            false,
            Some(format!("provider {} not permitted", model.provider)),
        );
    }
    if expectation.forbidden_models.contains(&model.model_id) {
        return (
            false,
            Some(format!("model {} is forbidden", model.model_id)),
        );
    }
    if expectation.min_context_tokens.is_some_and(|minimum| {
        minimum != 0
            && agentrouter_core::pydantic_integer_cmp(
                &model.context_window,
                &serde_json::Number::from(minimum),
            )
            .is_lt()
    }) {
        return (
            false,
            Some(format!(
                "context_window {} < {}",
                model.context_window,
                expectation.min_context_tokens.unwrap_or_default()
            )),
        );
    }
    (true, None)
}

pub(crate) fn round_to(value: f64, decimal_places: i32) -> f64 {
    let scale = 10_f64.powi(decimal_places);
    (value * scale).round_ties_even() / scale
}

/// Render the stable Markdown summary produced by Python
/// `evaluation.reports.render_markdown`.
pub fn render_markdown(result: &serde_json::Value) -> String {
    let mut lines = vec!["# Evaluation report".to_owned(), String::new()];
    if let Some(environment) = result
        .get("environment")
        .and_then(serde_json::Value::as_object)
    {
        lines.extend(["## Environment".to_owned(), String::new()]);
        for (key, value) in environment {
            lines.push(format!("- **{key}**: {}", python_string(value)));
        }
        lines.push(String::new());
    }

    lines.extend([
        "## Grade".to_owned(),
        String::new(),
        format!(
            "- **Grade /100 (unmeasured = 0):** {}",
            result_value(result, "grade_over_100")
        ),
        format!(
            "- **Grade of measured dimensions:** {} (measured {}/100 pts)",
            result_value(result, "grade_of_measured"),
            result_value(result, "possible_measured_points")
        ),
        format!(
            "- **Release ready:** {}",
            if truthy(result.get("release_ready")) {
                "YES"
            } else {
                "NO"
            }
        ),
        format!("- **Cases graded:** {}", result_value(result, "n_cases")),
        String::new(),
        "## Dimensions".to_owned(),
        String::new(),
        "| dimension | weight | status | score | achieved |".to_owned(),
        "|---|---|---|---|---|".to_owned(),
    ]);
    if let Some(dimensions) = result
        .get("dimensions")
        .and_then(serde_json::Value::as_object)
    {
        for (name, dimension) in dimensions {
            let score = dimension
                .get("score")
                .filter(|value| !value.is_null())
                .map(|value| format!("{:.3}", value.as_f64().unwrap_or(0.0)))
                .unwrap_or_else(|| "-".to_owned());
            lines.push(format!(
                "| {name} | {} | {} | {score} | {} |",
                result_value(dimension, "weight"),
                result_value(dimension, "status"),
                result_value(dimension, "achieved")
            ));
        }
    }
    lines.extend([String::new(), "## Release gates".to_owned(), String::new()]);
    if let Some(gates) = result
        .get("release_gates")
        .and_then(serde_json::Value::as_object)
    {
        for (name, ok) in gates {
            lines.push(format!(
                "- [{}] {name}",
                if truthy(Some(ok)) { "PASS" } else { "FAIL" }
            ));
        }
    }

    let metrics = result
        .get("classification")
        .unwrap_or(&serde_json::Value::Null);
    if metrics.as_object().is_some_and(|object| !object.is_empty()) {
        lines.extend([
            String::new(),
            "## Classification highlights".to_owned(),
            String::new(),
            format!("- task-type macro F1: {}", metrics["task_type"]["macro_f1"]),
            format!(
                "- high-risk recall: {}",
                result_value(metrics, "high_risk_recall")
            ),
            format!("- tool F1: {}", metrics["tools"]["f1"]),
            format!(
                "- gold-set context accuracy (in-sample): {}",
                metrics["context"]["accuracy"]
            ),
            format!(
                "- failed cases: {}",
                metrics
                    .get("failures")
                    .and_then(serde_json::Value::as_array)
                    .map_or(0, Vec::len)
            ),
        ]);
    }

    if let Some(generalization) = result.get("context_band_generalization") {
        if !generalization.is_null() {
            let current = &generalization["current_holdout"];
            let before = &generalization["pre_task004_holdout"];
            lines.extend([
                String::new(),
                "## Context-band generalization (frozen final holdout)".to_owned(),
                String::new(),
                format!(
                    "- holdout checksum: `{}`",
                    result_value(generalization, "holdout_sha256")
                ),
                format!(
                    "- current accuracy: {} (95% CI {})",
                    result_value(current, "accuracy"),
                    python_repr(&current["accuracy_ci95"])
                ),
                format!(
                    "- current macro-F1: {} (bootstrap 95% CI {})",
                    result_value(current, "macro_f1"),
                    python_repr(&current["macro_f1_bootstrap_ci95"])
                ),
                format!(
                    "- per-band recall: {}",
                    python_repr(&current["per_band_recall"])
                ),
                format!(
                    "- pre-TASK-004 accuracy: {}",
                    result_value(before, "accuracy")
                ),
                format!(
                    "- accuracy delta: {}",
                    result_value(&generalization["delta"], "accuracy")
                ),
            ]);
        }
    }

    lines.extend([String::new(), "## Limitations".to_owned(), String::new()]);
    if let Some(dimensions) = result
        .get("dimensions")
        .and_then(serde_json::Value::as_object)
    {
        for (name, dimension) in dimensions {
            if dimension.get("status").and_then(serde_json::Value::as_str) == Some("pending") {
                lines.push(format!(
                    "- `{name}` dimension not yet measured (evaluator pending)."
                ));
            }
        }
    }
    if let Some(limitations) = result
        .get("context_band_generalization")
        .and_then(|value| value.get("limitations"))
        .and_then(serde_json::Value::as_array)
    {
        for limitation in limitations {
            lines.push(format!("- {}", python_string(limitation)));
        }
    }
    let mut output = lines.join("\n");
    output.push('\n');
    output
}

/// Write all report artifacts emitted by Python `evaluation.reports`,
/// returning the same filename order without including machine-specific paths.
pub fn write_reports(
    result: &serde_json::Value,
    out_dir: &std::path::Path,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    use serde_json::{json, Map, Value};
    use std::fs;

    fs::create_dir_all(out_dir)?;
    let mut written = Vec::new();
    let mut payload = Map::new();
    payload.insert("report_schema_version".to_owned(), json!(1));
    if let Some(fields) = result.as_object() {
        for (key, value) in fields {
            payload.insert(key.clone(), value.clone());
        }
    }
    write_json_file(out_dir, "result.json", &Value::Object(payload))?;
    written.push("result.json".to_owned());

    let mut scorecard = Map::new();
    for key in [
        "grade_over_100",
        "grade_of_measured",
        "dimensions",
        "release_gates",
        "release_ready",
        "context_band_generalization",
    ] {
        scorecard.insert(
            key.to_owned(),
            result.get(key).cloned().unwrap_or(Value::Null),
        );
    }
    write_json_file(out_dir, "scorecard.json", &Value::Object(scorecard))?;
    written.push("scorecard.json".to_owned());

    fs::write(out_dir.join("report.md"), render_markdown(result))?;
    written.push("report.md".to_owned());

    let metrics = result.get("classification").unwrap_or(&Value::Null);
    let mut csv = vec![csv_record(&[
        "id".to_owned(),
        "prompt".to_owned(),
        "dimension".to_owned(),
        "expected".to_owned(),
        "predicted".to_owned(),
    ])];
    if let Some(failures) = metrics.get("failures").and_then(Value::as_array) {
        for failure in failures {
            if let Some(dimensions) = failure.get("failed").and_then(Value::as_array) {
                for dimension in dimensions {
                    let expected = dimension
                        .get("expected")
                        .and_then(Value::as_array)
                        .map(|values| {
                            values
                                .iter()
                                .map(python_string)
                                .collect::<Vec<_>>()
                                .join("|")
                        })
                        .unwrap_or_default();
                    let predicted = match dimension.get("predicted") {
                        Some(Value::Array(values)) => values
                            .iter()
                            .map(python_string)
                            .collect::<Vec<_>>()
                            .join("|"),
                        Some(value) => python_string(value),
                        None => String::new(),
                    };
                    csv.push(csv_record(&[
                        result_value(failure, "id"),
                        result_value(failure, "prompt"),
                        result_value(dimension, "dim"),
                        expected,
                        predicted,
                    ]));
                }
            }
        }
    }
    fs::write(out_dir.join("failures.csv"), csv.concat())?;
    written.push("failures.csv".to_owned());

    let generalization = result
        .get("context_band_generalization")
        .filter(|value| !value.is_null());
    let holdout_failures = generalization
        .and_then(|value| value.get("current_holdout"))
        .and_then(|value| value.get("failures"))
        .and_then(Value::as_array);
    let mut csv = vec![csv_record(&[
        "id".to_owned(),
        "category".to_owned(),
        "expected".to_owned(),
        "predicted".to_owned(),
    ])];
    if let Some(failures) = holdout_failures {
        for failure in failures {
            csv.push(csv_record(&[
                result_value(failure, "id"),
                result_value(failure, "category"),
                result_value(failure, "expected"),
                result_value(failure, "predicted"),
            ]));
        }
    }
    fs::write(
        out_dir.join("context_band_holdout_failures.csv"),
        csv.concat(),
    )?;
    written.push("context_band_holdout_failures.csv".to_owned());

    for (key, filename) in [
        ("confusion_task_type", "confusion_task_type.csv"),
        ("confusion_risk", "confusion_risk.csv"),
    ] {
        if let Some(matrix) = metrics.get(key).and_then(Value::as_object) {
            fs::write(out_dir.join(filename), confusion_csv(matrix))?;
            written.push(filename.to_owned());
        }
    }
    Ok(written)
}

#[cfg(test)]
mod performance_contract_tests {
    use std::cell::Cell;

    #[test]
    fn injected_classifier_runs_once_for_each_performance_task() {
        let models = crate::evaluators_api::load_seed_models().expect("packaged seed catalog");
        let tasks = vec!["first task".to_owned(), "second task".to_owned()];
        let calls = Cell::new(0);
        let report = crate::evaluate_performance_with(&models, &tasks, |task| {
            calls.set(calls.get() + 1);
            agentrouter_classifier::classify(
                task,
                &agentrouter_classifier::ClassifyOptions::default(),
            )
        });

        assert_eq!(calls.get(), tasks.len());
        assert_eq!(report["detail"]["n_samples"], tasks.len());
        assert!(report["score"]
            .as_f64()
            .is_some_and(|score| (0.0..=1.0).contains(&score)));
    }
}

fn write_json_file(
    out_dir: &std::path::Path,
    filename: &str,
    value: &serde_json::Value,
) -> Result<(), Box<dyn std::error::Error>> {
    std::fs::write(out_dir.join(filename), serde_json::to_string_pretty(value)?)?;
    Ok(())
}

fn csv_record(fields: &[String]) -> String {
    let mut row = fields
        .iter()
        .map(|field| {
            if field.contains([',', '"', '\r', '\n']) {
                format!("\"{}\"", field.replace('"', "\"\""))
            } else {
                field.clone()
            }
        })
        .collect::<Vec<_>>()
        .join(",");
    row.push_str("\r\n");
    row
}

fn confusion_csv(matrix: &serde_json::Map<String, serde_json::Value>) -> String {
    use std::collections::BTreeSet;

    let mut labels: BTreeSet<String> = matrix.keys().cloned().collect();
    for row in matrix.values().filter_map(serde_json::Value::as_object) {
        labels.extend(row.keys().cloned());
    }
    let labels: Vec<_> = labels.into_iter().collect();
    let mut output = vec![csv_record(
        &std::iter::once("gold\\pred".to_owned())
            .chain(labels.iter().cloned())
            .collect::<Vec<_>>(),
    )];
    for gold in &labels {
        let row = matrix.get(gold).and_then(serde_json::Value::as_object);
        let mut fields = vec![gold.clone()];
        fields.extend(labels.iter().map(|predicted| {
            row.and_then(|row| row.get(predicted))
                .and_then(serde_json::Value::as_i64)
                .unwrap_or(0)
                .to_string()
        }));
        output.push(csv_record(&fields));
    }
    output.concat()
}

fn result_value(value: &serde_json::Value, key: &str) -> String {
    value
        .get(key)
        .map_or_else(|| "None".to_owned(), python_string)
}

fn python_string(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Null => "None".to_owned(),
        serde_json::Value::Bool(true) => "True".to_owned(),
        serde_json::Value::Bool(false) => "False".to_owned(),
        serde_json::Value::String(text) => text.clone(),
        serde_json::Value::Number(number) => number.to_string(),
        _ => python_repr(value),
    }
}

fn python_repr(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Null => "None".to_owned(),
        serde_json::Value::Bool(true) => "True".to_owned(),
        serde_json::Value::Bool(false) => "False".to_owned(),
        serde_json::Value::String(text) => {
            format!("'{}'", text.replace('\\', "\\\\").replace('\'', "\\'"))
        }
        serde_json::Value::Number(number) => number.to_string(),
        serde_json::Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(python_repr)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        serde_json::Value::Object(values) => format!(
            "{{{}}}",
            values
                .iter()
                .map(|(key, value)| format!(
                    "{}: {}",
                    python_repr(&serde_json::Value::String(key.clone())),
                    python_repr(value)
                ))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}

fn truthy(value: Option<&serde_json::Value>) -> bool {
    match value {
        None | Some(serde_json::Value::Null) | Some(serde_json::Value::Bool(false)) => false,
        Some(serde_json::Value::Number(number)) => number.as_f64().unwrap_or(0.0) != 0.0,
        Some(serde_json::Value::String(text)) => !text.is_empty(),
        Some(serde_json::Value::Array(values)) => !values.is_empty(),
        Some(serde_json::Value::Object(values)) => !values.is_empty(),
        Some(serde_json::Value::Bool(true)) => true,
    }
}

pub fn profile_datasets(profile: &str) -> Result<&'static [&'static str], String> {
    match profile {
        "fast" | "pr" => Ok(&DATASET_NAMES[..1]),
        "nightly" => Ok(&DATASET_NAMES[..4]),
        "release" => Ok(&DATASET_NAMES[..5]),
        "full" => Ok(&DATASET_NAMES),
        _ => Err(format!(
            "unknown profile '{profile}'. Known: {}",
            PROFILE_NAMES.join(", ")
        )),
    }
}

pub fn adapter_descriptor(name: &str) -> Result<&'static AdapterDescriptor, String> {
    ADAPTERS
        .iter()
        .find(|descriptor| descriptor.name == name)
        .ok_or_else(|| {
            format!(
                "unknown dataset '{name}'. Known: {}",
                DATASET_NAMES.join(", ")
            )
        })
}

#[derive(Debug, Clone, Copy, Default, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AnnotationMethod {
    Human,
    #[default]
    ModelAssisted,
    Heuristic,
    DatasetNative,
}

#[derive(Debug, Clone, Copy, Default, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReviewStatus {
    #[default]
    Pending,
    Approved,
    Rejected,
}

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Provenance {
    #[serde(default)]
    pub method: AnnotationMethod,
    #[serde(default)]
    pub reviewer: Option<String>,
    #[serde(default)]
    pub source_license: Option<String>,
    #[serde(default)]
    pub source_record_id: Option<String>,
    #[serde(default)]
    pub retrieved: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ExpectedClassification {
    #[serde(default)]
    pub task_types: Vec<TaskType>,
    #[serde(default)]
    pub complexities: Vec<Level>,
    #[serde(default)]
    pub risks: Vec<Level>,
    #[serde(default)]
    pub context_bands: Vec<ContextBand>,
    #[serde(default)]
    pub output_types: Vec<OutputType>,
    #[serde(default)]
    pub required_tools: Vec<String>,
    #[serde(default)]
    pub approval_levels: Vec<ApprovalLevel>,
}

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct RoutingExpectation {
    #[serde(default)]
    pub minimum_ability: BTreeMap<String, i64>,
    #[serde(default)]
    pub acceptable_pricing_tiers: Vec<PricingTier>,
    #[serde(default)]
    pub permitted_providers: Vec<String>,
    #[serde(default)]
    pub forbidden_models: Vec<String>,
    #[serde(default)]
    pub required_tools: Vec<String>,
    #[serde(default)]
    pub min_context_tokens: Option<i64>,
}

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SafetyExpectation {
    #[serde(default)]
    pub auto_execute_allowed: Option<bool>,
    #[serde(default)]
    pub must_require_human_approval: bool,
}

/// Normalized evaluation record; serialized field names and defaults mirror
/// `agentrouter.evaluation.schema.EvaluationCase`.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct EvaluationCase {
    pub id: String,
    pub dataset: String,
    #[serde(deserialize_with = "deserialize_nonempty_task")]
    pub task: String,
    #[serde(default)]
    pub dataset_version: Option<String>,
    #[serde(default)]
    pub source: Option<String>,
    #[serde(default)]
    pub source_split: Option<String>,
    #[serde(default = "default_language")]
    pub language: String,
    #[serde(default)]
    pub domain: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub paraphrase_group: Option<String>,
    #[serde(default)]
    pub expected: ExpectedClassification,
    #[serde(default)]
    pub routing: Option<RoutingExpectation>,
    #[serde(default)]
    pub safety: Option<SafetyExpectation>,
    #[serde(default)]
    pub context_tokens: Option<i64>,
    #[serde(default)]
    pub cost_metadata: BTreeMap<String, serde_json::Value>,
    #[serde(default)]
    pub model_outcomes: BTreeMap<String, serde_json::Value>,
    #[serde(default)]
    pub provenance: Provenance,
    #[serde(default)]
    pub review_status: ReviewStatus,
    #[serde(default)]
    pub checksum: Option<String>,
    #[serde(default)]
    pub notes: Option<String>,
}

/// Shared metadata contract from `evaluation.base.DatasetMetadata`.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct EvaluationDatasetMetadata {
    pub name: String,
    pub version: String,
    pub license: String,
    pub source: String,
    pub description: String,
    #[serde(default)]
    pub requires_network: bool,
    #[serde(default)]
    pub requires_docker: bool,
    #[serde(default = "default_languages")]
    pub languages: Vec<String>,
}

fn default_languages() -> Vec<String> {
    vec!["en".to_string()]
}

/// Load a normalized JSONL smoke fixture using the shared Python adapter
/// contract: blank lines are ignored, each record is validated, and checksums
/// are attached before adapter-level uniqueness checks.
pub fn load_adapter_fixture(
    path: &Path,
    metadata: &EvaluationDatasetMetadata,
) -> Result<Vec<EvaluationCase>, String> {
    let contents = std::fs::read_to_string(path)
        .map_err(|_| format!("{}: fixture not found at {}", metadata.name, path.display()))?;
    let mut cases = Vec::new();
    for line in contents
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
    {
        let case: EvaluationCase = serde_json::from_str(line)
            .map_err(|error| format!("{}: invalid fixture record: {error}", metadata.name))?;
        cases.push(case.with_checksum());
    }
    validate_adapter_cases(metadata, &cases)?;
    Ok(cases)
}

fn validate_adapter_cases(
    metadata: &EvaluationDatasetMetadata,
    cases: &[EvaluationCase],
) -> Result<(), String> {
    let mut ids = BTreeSet::new();
    let mut hashes = BTreeSet::new();
    for case in cases {
        if !ids.insert(&case.id) {
            return Err(format!("{}: duplicate case ids", metadata.name));
        }
        hashes.insert(case.task_hash());
    }
    if metadata.source.is_empty() || metadata.license.is_empty() {
        return Err(format!(
            "{}: missing source/license metadata",
            metadata.name
        ));
    }
    if hashes.len() != cases.len() {
        return Err(format!(
            "{}: {} exact-duplicate task(s)",
            metadata.name,
            cases.len() - hashes.len()
        ));
    }
    Ok(())
}

pub fn adapter_availability(path: &Path) -> &'static str {
    if path.exists() {
        "fixture_only"
    } else {
        "skipped_external"
    }
}

/// Rust has no Hugging Face `datasets` runtime. Real mode therefore remains
/// an explicit skipped-external result and never falls back to fixture data.
pub fn adapter_real_availability(name: &str, hf_repo: Option<&str>) -> (bool, String) {
    if hf_repo.is_none() {
        return (
            false,
            format!("{name}: no real loader configured (source unverified)"),
        );
    }
    (
        false,
        "the `datasets` library is not installed (pip install -e '.[eval]')".to_string(),
    )
}

pub fn load_adapter_dataset(
    path: &Path,
    metadata: &EvaluationDatasetMetadata,
    hf_repo: Option<&str>,
    source: &str,
) -> Result<Vec<EvaluationCase>, String> {
    match source {
        "fixture" => load_adapter_fixture(path, metadata),
        "real" => {
            let (available, reason) = adapter_real_availability(&metadata.name, hf_repo);
            if available {
                Err(format!(
                    "{}: Rust real dataset loading is unsupported",
                    metadata.name
                ))
            } else {
                Err(format!("{}: {reason}", metadata.name))
            }
        }
        _ => Err(format!("{}: unknown source '{source}'", metadata.name)),
    }
}

pub fn sample_adapter_cases(
    cases: &[EvaluationCase],
    limit: Option<i64>,
    seed: i64,
) -> Vec<EvaluationCase> {
    let Some(limit) = limit else {
        return cases.to_vec();
    };
    deterministic_sample(cases, limit, seed, |case| case.id.clone())
        .into_iter()
        .cloned()
        .collect()
}

pub fn adapter_checksum(cases: &[EvaluationCase]) -> String {
    let mut hashes: Vec<_> = cases.iter().map(EvaluationCase::task_hash).collect();
    hashes.sort();
    let payload = format!(
        "[{}]",
        hashes
            .iter()
            .map(|hash| format!("\"{hash}\""))
            .collect::<Vec<_>>()
            .join(", ")
    );
    let digest = Sha256::digest(payload.as_bytes());
    digest[..8]
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

pub fn describe_adapter(
    path: &Path,
    metadata: &EvaluationDatasetMetadata,
    hf_repo: Option<&str>,
) -> serde_json::Value {
    let (real_available, real_reason) = adapter_real_availability(&metadata.name, hf_repo);
    serde_json::json!({
        "name": metadata.name,
        "version": metadata.version,
        "license": metadata.license,
        "source": metadata.source,
        "availability": adapter_availability(path),
        "real_available": real_available,
        "real_reason": real_reason,
        "hf_repo": hf_repo,
        "requires_network": metadata.requires_network,
        "requires_docker": metadata.requires_docker,
        "languages": metadata.languages,
    })
}

const CLINC_INTENT_HINTS: &[(&str, &[&str])] = &[
    ("translate", &["writing", "general"]),
    ("definition", &["general", "writing"]),
    ("spelling", &["writing"]),
    ("calculator", &["general"]),
    ("math", &["reasoning", "general"]),
    ("how_busy", &["general"]),
    ("meaning_of_life", &["general"]),
    ("text", &["writing"]),
    ("todo", &["general"]),
    ("reminder", &["general"]),
    ("calendar", &["general"]),
];

/// Match `CLINC150Adapter.map_intent`, retaining its ordered substring rules.
pub fn clinc150_map_intent(intent: &str) -> (Vec<String>, bool) {
    for (hint, families) in CLINC_INTENT_HINTS {
        if intent.contains(hint) {
            return (
                families.iter().map(|value| (*value).to_string()).collect(),
                true,
            );
        }
    }
    (vec!["general".to_string()], false)
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Clinc150RawRow {
    pub text: String,
    pub intent: usize,
}

/// Normalize caller-supplied rows from the CLINC150 `plus` test split.
/// Dataset fetching remains an explicit external-runtime responsibility.
pub fn normalize_clinc150_rows(
    label_names: &[String],
    rows: &[Clinc150RawRow],
) -> Result<Vec<EvaluationCase>, String> {
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    for (index, row) in rows.iter().enumerate() {
        let task = row.text.trim().to_string();
        if !seen.insert(task.to_lowercase()) {
            continue;
        }
        let intent = label_names.get(row.intent).ok_or_else(|| {
            format!(
                "clinc150: intent index {} is outside label names",
                row.intent
            )
        })?;
        let is_oos = intent == "oos";
        let (families, curated) = if is_oos {
            (vec!["general".to_string()], false)
        } else {
            clinc150_map_intent(intent)
        };
        let tags = if is_oos {
            vec!["out-of-scope".to_string()]
        } else if curated {
            vec![intent.clone()]
        } else {
            vec![intent.clone(), "needs-review".to_string()]
        };
        out.push(EvaluationCase {
            id: format!("clinc-{index}"),
            dataset: "clinc150".to_string(),
            task,
            dataset_version: Some("plus".to_string()),
            source: Some("https://huggingface.co/datasets/clinc_oos".to_string()),
            source_split: Some("test".to_string()),
            language: default_language(),
            domain: Some(if is_oos { "oos" } else { "intent" }.to_string()),
            tags,
            paraphrase_group: None,
            expected: ExpectedClassification {
                task_types: families
                    .into_iter()
                    .map(|value| match value.as_str() {
                        "analysis" => TaskType::Analysis,
                        "coding" => TaskType::Coding,
                        "general" => TaskType::General,
                        "reasoning" => TaskType::Reasoning,
                        "summarization" => TaskType::Summarization,
                        "writing" => TaskType::Writing,
                        _ => unreachable!("CLINC intent map contains a known task family"),
                    })
                    .collect(),
                ..ExpectedClassification::default()
            },
            routing: None,
            safety: None,
            context_tokens: None,
            cost_metadata: BTreeMap::new(),
            model_outcomes: BTreeMap::new(),
            provenance: Provenance {
                method: AnnotationMethod::Heuristic,
                reviewer: None,
                source_license: Some("CC BY 3.0".to_string()),
                source_record_id: Some(index.to_string()),
                retrieved: None,
            },
            review_status: ReviewStatus::Pending,
            checksum: None,
            notes: Some(format!("clinc_intent={intent}")),
        });
    }
    let mut normalized = Vec::new();
    let mut hashes = BTreeSet::new();
    for case in out {
        if hashes.insert(case.task_hash()) {
            normalized.push(case.with_checksum());
        }
    }
    Ok(normalized)
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Banking77RawRow {
    pub text: String,
    pub label: usize,
}

/// Normalize caller-supplied rows from the PolyAI/Banking77 test split.
pub fn normalize_banking77_rows(
    label_names: &[String],
    rows: &[Banking77RawRow],
) -> Result<Vec<EvaluationCase>, String> {
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    for (index, row) in rows.iter().enumerate() {
        let task = row.text.trim().to_string();
        if !seen.insert(task.to_lowercase()) {
            continue;
        }
        let intent = label_names.get(row.label).ok_or_else(|| {
            format!(
                "banking77: label index {} is outside label names",
                row.label
            )
        })?;
        out.push(EvaluationCase {
            id: format!("banking77-{index}"),
            dataset: "banking77".to_string(),
            task,
            dataset_version: Some("v1".to_string()),
            source: Some("https://huggingface.co/datasets/PolyAI/banking77".to_string()),
            source_split: Some("test".to_string()),
            language: default_language(),
            domain: Some("banking".to_string()),
            tags: vec![intent.clone()],
            paraphrase_group: None,
            expected: ExpectedClassification {
                task_types: vec![TaskType::General, TaskType::Analysis],
                risks: vec![Level::Low],
                ..ExpectedClassification::default()
            },
            routing: None,
            safety: None,
            context_tokens: None,
            cost_metadata: BTreeMap::new(),
            model_outcomes: BTreeMap::new(),
            provenance: Provenance {
                method: AnnotationMethod::Heuristic,
                reviewer: None,
                source_license: Some("MIT".to_string()),
                source_record_id: Some(index.to_string()),
                retrieved: None,
            },
            review_status: ReviewStatus::Pending,
            checksum: None,
            notes: Some(format!("banking77_intent={intent}")),
        });
    }
    let mut normalized = Vec::new();
    let mut hashes = BTreeSet::new();
    for case in out {
        if hashes.insert(case.task_hash()) {
            normalized.push(case.with_checksum());
        }
    }
    Ok(normalized)
}

#[derive(Debug, Deserialize)]
pub struct MassiveRawRow {
    pub utt: String,
    #[serde(default = "empty_json_string")]
    pub scenario: serde_json::Value,
    #[serde(default = "empty_json_string")]
    pub intent: serde_json::Value,
}

fn empty_json_string() -> serde_json::Value {
    serde_json::Value::String(String::new())
}

/// Normalize MASSIVE rows for selected short language codes. Each locale batch
/// corresponds to one `_hf_load(split="test")` result from Python.
pub fn normalize_massive_rows(
    languages: Option<&[String]>,
    datasets: &BTreeMap<String, Vec<MassiveRawRow>>,
) -> Result<Vec<EvaluationCase>, String> {
    let requested = languages
        .map(<[String]>::to_vec)
        .unwrap_or_else(|| vec!["en".into(), "hi".into(), "fr".into()]);
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    let mut hashes = BTreeSet::new();
    for lang in requested {
        let locale = match lang.as_str() {
            "en" => "en-US",
            "hi" => "hi-IN",
            "fr" => "fr-FR",
            _ => return Err(format!("massive: no HF locale mapping for '{lang}'")),
        };
        let rows = datasets
            .get(locale)
            .ok_or_else(|| format!("massive: missing row batch for locale '{locale}'"))?;
        for (index, row) in rows.iter().enumerate() {
            let task = row.utt.trim().to_string();
            if task.is_empty() {
                return Err("massive: task must be non-empty".to_string());
            }
            let dedup_key = format!("{lang}:{}", task.to_lowercase());
            if !seen.insert(dedup_key) {
                continue;
            }
            let scenario = python_string(&row.scenario);
            let intent = python_string(&row.intent);
            let case = EvaluationCase {
                id: format!("massive-{lang}-{index}"),
                dataset: "massive".to_string(),
                task,
                dataset_version: Some("1.1".to_string()),
                source: Some("https://huggingface.co/datasets/AmazonScience/massive".to_string()),
                source_split: Some("test".to_string()),
                language: lang.clone(),
                domain: Some(scenario),
                tags: vec![format!("intent:{intent}")],
                paraphrase_group: None,
                expected: ExpectedClassification {
                    task_types: vec![TaskType::General],
                    ..ExpectedClassification::default()
                },
                routing: None,
                safety: None,
                context_tokens: None,
                cost_metadata: BTreeMap::new(),
                model_outcomes: BTreeMap::new(),
                provenance: Provenance {
                    method: AnnotationMethod::Heuristic,
                    reviewer: None,
                    source_license: Some("CC BY 4.0".to_string()),
                    source_record_id: Some(format!("{locale}:{index}")),
                    retrieved: None,
                },
                review_status: ReviewStatus::Pending,
                checksum: None,
                notes: Some(format!("massive_locale={locale}")),
            };
            if hashes.insert(case.task_hash()) {
                out.push(case.with_checksum());
            }
        }
    }
    Ok(out)
}

const LONGBENCH_CONTEXT_BUCKETS: [(&str, i64, i64); 5] = [
    ("under-8k", 0, 8_000),
    ("8k-32k", 8_000, 32_000),
    ("32k-128k", 32_000, 128_000),
    ("128k-512k", 128_000, 512_000),
    ("over-512k", 512_000, 1_000_000_000),
];

/// Match the reporting buckets used by `LongBenchV2Adapter.bucket_for`.
pub fn longbench_bucket_for(tokens: i64) -> &'static str {
    LONGBENCH_CONTEXT_BUCKETS
        .iter()
        .find(|(_, low, high)| *low <= tokens && tokens < *high)
        .map_or(LONGBENCH_CONTEXT_BUCKETS[0].0, |(label, _, _)| label)
}

fn missing_longbench_id() -> serde_json::Value {
    serde_json::Value::String("__AGENTROUTER_MISSING_LONGBENCH_ID__".to_string())
}

fn missing_longbench_domain() -> serde_json::Value {
    serde_json::Value::String("__AGENTROUTER_MISSING_LONGBENCH_DOMAIN__".to_string())
}

#[derive(Debug, Deserialize)]
pub struct LongBenchRawRow {
    #[serde(default)]
    pub question: Option<String>,
    #[serde(default)]
    pub context: Option<String>,
    #[serde(default = "missing_longbench_domain")]
    pub domain: serde_json::Value,
    #[serde(default = "empty_json_string")]
    pub difficulty: serde_json::Value,
    #[serde(rename = "_id", default = "missing_longbench_id")]
    pub record_id: serde_json::Value,
}

/// Normalize caller-supplied LongBench v2 rows. Context lengths use the same
/// word-count estimate as Python; model-based long-context evaluation remains
/// outside this data-preparation function.
pub fn normalize_longbench_rows(rows: &[LongBenchRawRow]) -> Vec<EvaluationCase> {
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    let mut hashes = BTreeSet::new();
    for (index, row) in rows.iter().enumerate() {
        let question = row.question.as_deref().unwrap_or_default().trim();
        if question.is_empty() || !seen.insert(question.to_lowercase()) {
            continue;
        }
        let context = row.context.as_deref().unwrap_or_default();
        let words = context.split_whitespace().count();
        let tokens = (words as f64 * 1.3) as i64;
        let band = if tokens < 8_000 {
            "small"
        } else if tokens < 32_000 {
            "medium"
        } else {
            "large"
        };
        let record_id = if row.record_id.as_str() == Some("__AGENTROUTER_MISSING_LONGBENCH_ID__") {
            index.to_string()
        } else {
            python_string(&row.record_id)
        };
        let domain_missing =
            row.domain.as_str() == Some("__AGENTROUTER_MISSING_LONGBENCH_DOMAIN__");
        let domain = if domain_missing {
            String::new()
        } else {
            python_string(&row.domain)
        };
        let note_domain = if domain_missing {
            "None".to_string()
        } else {
            python_string(&row.domain)
        };
        let difficulty = python_string(&row.difficulty);
        let case = EvaluationCase {
            id: format!("longbench-{record_id}"),
            dataset: "longbench-v2".to_string(),
            task: question.to_string(),
            dataset_version: Some("v2".to_string()),
            source: Some("https://huggingface.co/datasets/THUDM/LongBench-v2".to_string()),
            source_split: Some("train".to_string()),
            language: default_language(),
            domain: Some(domain.clone()),
            tags: vec![
                "long-context".to_string(),
                longbench_bucket_for(tokens).to_string(),
                difficulty,
            ],
            paraphrase_group: None,
            expected: ExpectedClassification {
                context_bands: vec![match band {
                    "small" => ContextBand::Small,
                    "medium" => ContextBand::Medium,
                    _ => ContextBand::Large,
                }],
                ..ExpectedClassification::default()
            },
            routing: None,
            safety: None,
            context_tokens: Some(tokens),
            cost_metadata: BTreeMap::new(),
            model_outcomes: BTreeMap::new(),
            provenance: Provenance {
                method: AnnotationMethod::DatasetNative,
                reviewer: None,
                source_license: Some("LongBench v2 (see dataset card)".to_string()),
                source_record_id: Some(record_id.clone()),
                retrieved: None,
            },
            review_status: ReviewStatus::Pending,
            checksum: None,
            notes: Some(format!("longbench_domain={note_domain} words={words}")),
        };
        if hashes.insert(case.task_hash()) {
            out.push(case.with_checksum());
        }
    }
    out
}

fn missing_swebench_field() -> serde_json::Value {
    serde_json::Value::String("__AGENTROUTER_MISSING_SWEBENCH_FIELD__".to_string())
}

#[derive(Debug, Deserialize)]
pub struct SWEBenchRawRow {
    #[serde(default)]
    pub problem_statement: Option<String>,
    #[serde(default = "missing_swebench_field")]
    pub instance_id: serde_json::Value,
    #[serde(default = "missing_swebench_field")]
    pub repo: serde_json::Value,
    #[serde(default = "missing_swebench_field")]
    pub base_commit: serde_json::Value,
}

fn value_if_present(value: &serde_json::Value, missing_value: &str) -> String {
    if value.as_str() == Some("__AGENTROUTER_MISSING_SWEBENCH_FIELD__") {
        missing_value.to_string()
    } else {
        python_string(value)
    }
}

/// Prepare caller-supplied SWE-bench Lite test rows for classification and
/// routing evaluation. Docker issue solving remains a separate external run.
pub fn normalize_swebench_rows(rows: &[SWEBenchRawRow]) -> Vec<EvaluationCase> {
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    let mut hashes = BTreeSet::new();
    for (index, row) in rows.iter().enumerate() {
        let problem = row.problem_statement.as_deref().unwrap_or_default().trim();
        if problem.is_empty() || !seen.insert(problem.to_lowercase()) {
            continue;
        }
        let id_value = value_if_present(&row.instance_id, &index.to_string());
        let repo_tag = value_if_present(&row.repo, "");
        let repo_note = value_if_present(&row.repo, "None");
        let base_commit_note = value_if_present(&row.base_commit, "None");
        let case = EvaluationCase {
            id: format!("swebench-{id_value}"),
            dataset: "swebench".to_string(),
            task: problem.to_string(),
            dataset_version: Some("lite".to_string()),
            source: Some("https://www.swebench.com".to_string()),
            source_split: Some("test".to_string()),
            language: default_language(),
            domain: Some("software-engineering".to_string()),
            tags: vec!["swe-bench".to_string(), "issue".to_string(), repo_tag],
            paraphrase_group: None,
            expected: ExpectedClassification {
                task_types: vec![TaskType::Coding],
                ..ExpectedClassification::default()
            },
            routing: Some(RoutingExpectation {
                minimum_ability: BTreeMap::from([("coding".to_string(), 7)]),
                ..RoutingExpectation::default()
            }),
            safety: None,
            context_tokens: None,
            cost_metadata: BTreeMap::new(),
            model_outcomes: BTreeMap::new(),
            provenance: Provenance {
                method: AnnotationMethod::DatasetNative,
                reviewer: None,
                source_license: Some("SWE-bench (MIT code; per-repo licenses apply)".to_string()),
                source_record_id: Some(id_value),
                retrieved: None,
            },
            review_status: ReviewStatus::Pending,
            checksum: None,
            notes: Some(format!("repo={repo_note} base_commit={base_commit_note}")),
        };
        if hashes.insert(case.task_hash()) {
            out.push(case.with_checksum());
        }
    }
    out
}

const LLMROUTERBENCH_MAPPING_NOTE: &str =
    "Provide a model-mapping file translating LLMRouterBench model keys to registry entries; commercial names never appear in routing logic.";

pub fn llmrouterbench_describe(
    path: &Path,
    metadata: &EvaluationDatasetMetadata,
) -> serde_json::Value {
    let mut description = describe_adapter(path, metadata, None);
    description["model_mapping_required"] = serde_json::Value::Bool(true);
    description["model_mapping_note"] =
        serde_json::Value::String(LLMROUTERBENCH_MAPPING_NOTE.to_string());
    description
}

pub fn llmrouterbench_full_run_status() -> serde_json::Value {
    serde_json::json!({
        "status": "SKIPPED_EXTERNAL",
        "reason": "The full LLMRouterBench run consumes the benchmark's per-model outputs (keyed by commercial model names) and a model-mapping file onto registry entries, then scores router cost/quality. Cloning the repo and supplying the mapping are out of scope for offline CI.",
        "commands": [
            "git clone <LLMRouterBench repo> llmrouterbench && cd llmrouterbench",
            "pip install -r requirements.txt",
            "# create model_mapping.yaml mapping benchmark model keys -> registry model keys (provider/model_id)",
            "python -m agentrouter.evaluation.cli run --dataset llmrouterbench --model-mapping model_mapping.yaml"
        ]
    })
}

pub fn twinrouterbench_full_run_status() -> serde_json::Value {
    serde_json::json!({
        "status": "SKIPPED_EXTERNAL",
        "reason": "The dynamic track replays full multi-agent workflows through a containerized agent runtime to measure live per-step routing. It requires a running Docker daemon and the benchmark's workflow images, neither available in offline CI. The static track is covered here from the committed fixture.",
        "commands": [
            "git clone <TwinRouterBench repo> twinrouterbench && cd twinrouterbench",
            "# install and start Docker (daemon must be running)",
            "docker info",
            "docker compose up -d  # bring up the workflow runtime",
            "python -m twinrouterbench.run --track dynamic --router agentrouter"
        ]
    })
}

#[derive(Debug, Deserialize)]
struct AgentRouterGoldDocument {
    #[serde(default = "default_gold_version")]
    version: u64,
    cases: Vec<AgentRouterGoldRow>,
}

fn default_gold_version() -> u64 {
    1
}

#[derive(Debug, Deserialize)]
struct AgentRouterGoldRow {
    id: String,
    prompt: String,
    #[serde(default)]
    task_type: Vec<TaskType>,
    #[serde(default)]
    complexity: Vec<Level>,
    #[serde(default)]
    risk: Vec<Level>,
    #[serde(default)]
    output_type: Vec<OutputType>,
    #[serde(default)]
    tools: Vec<String>,
    #[serde(default)]
    context_band: Vec<ContextBand>,
}

/// Load the committed human-labelled classifier gold set, mirroring
/// `AgentRouterGoldAdapter.load()` including approval derivation, provenance,
/// checksums, and adapter-level uniqueness validation.
pub fn load_agentrouter_gold(path: &Path) -> Result<Vec<EvaluationCase>, String> {
    let source = "benchmarks/classifier_gold_v1.yaml";
    let contents = std::fs::read_to_string(path)
        .map_err(|_| format!("gold benchmark not found: {}", path.display()))?;
    let document: AgentRouterGoldDocument = serde_yaml::from_str(&contents)
        .map_err(|_| format!("{}: expected a mapping with a 'cases' list", path.display()))?;

    let cases = document
        .cases
        .into_iter()
        .map(|row| {
            let approval_levels = row
                .risk
                .iter()
                .map(|risk| match risk {
                    Level::Low => ApprovalLevel::Auto,
                    Level::Medium => ApprovalLevel::Notify,
                    Level::High => ApprovalLevel::HumanApprovalRequired,
                })
                .collect();
            EvaluationCase {
                id: row.id,
                dataset: "agentrouter-gold".to_string(),
                task: row.prompt,
                dataset_version: Some(format!("v{}", document.version)),
                source: Some(source.to_string()),
                source_split: None,
                language: default_language(),
                domain: None,
                tags: Vec::new(),
                paraphrase_group: None,
                expected: ExpectedClassification {
                    task_types: row.task_type,
                    complexities: row.complexity,
                    risks: row.risk,
                    context_bands: row.context_band,
                    output_types: row.output_type,
                    required_tools: row.tools,
                    approval_levels,
                },
                routing: None,
                safety: None,
                context_tokens: None,
                cost_metadata: BTreeMap::new(),
                model_outcomes: BTreeMap::new(),
                provenance: Provenance {
                    method: AnnotationMethod::Human,
                    reviewer: None,
                    source_license: Some("MIT".to_string()),
                    source_record_id: None,
                    retrieved: None,
                },
                review_status: ReviewStatus::Approved,
                checksum: None,
                notes: None,
            }
            .with_checksum()
        })
        .collect::<Vec<_>>();

    let mut ids = BTreeSet::new();
    let mut hashes = BTreeSet::new();
    for case in &cases {
        if !ids.insert(&case.id) {
            return Err("agentrouter-gold: duplicate case ids".to_string());
        }
        hashes.insert(case.task_hash());
    }
    if hashes.len() != cases.len() {
        return Err(format!(
            "agentrouter-gold: {} exact-duplicate task(s)",
            cases.len() - hashes.len()
        ));
    }
    Ok(cases)
}

pub fn agentrouter_gold_availability(path: &Path) -> &'static str {
    if path.exists() {
        "ready"
    } else {
        "skipped_external"
    }
}

pub fn agentrouter_gold_metadata() -> serde_json::Value {
    serde_json::json!({
        "name": "agentrouter-gold",
        "version": "v1",
        "license": "project-internal (MIT repo)",
        "source": "benchmarks/classifier_gold_v1.yaml",
        "description": "Human-expectation gold labels for the 7-dimension classifier.",
        "requires_network": false,
        "requires_docker": false,
        "languages": ["en"],
    })
}

pub fn agentrouter_gold_describe(path: &Path) -> serde_json::Value {
    let mut description = agentrouter_gold_metadata();
    description
        .as_object_mut()
        .expect("gold metadata is an object")
        .remove("description");
    description["availability"] = serde_json::json!(agentrouter_gold_availability(path));
    description["real_available"] = serde_json::json!(false);
    description["real_reason"] =
        serde_json::json!("agentrouter-gold: no real loader configured (source unverified)");
    description["hf_repo"] = serde_json::Value::Null;
    description
}

pub fn agentrouter_gold_sample(
    path: &Path,
    limit: Option<i64>,
    seed: i64,
) -> Result<Vec<EvaluationCase>, String> {
    let cases = load_agentrouter_gold(path)?;
    let Some(limit) = limit else {
        return Ok(cases);
    };
    Ok(
        deterministic_sample(&cases, limit, seed, |case| case.id.clone())
            .into_iter()
            .cloned()
            .collect(),
    )
}

pub fn agentrouter_gold_checksum(path: &Path) -> Result<String, String> {
    let cases = load_agentrouter_gold(path)?;
    Ok(adapter_checksum(&cases))
}

fn deserialize_nonempty_task<'de, D>(deserializer: D) -> Result<String, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let task = String::deserialize(deserializer)?;
    if task.chars().all(is_python_whitespace) {
        return Err(serde::de::Error::custom("task must be non-empty"));
    }
    Ok(task)
}

impl EvaluationCase {
    /// Enforce the Python model's semantic task validator.
    pub fn validate(&self) -> Result<(), &'static str> {
        if self.task.chars().all(is_python_whitespace) {
            Err("task must be non-empty")
        } else {
            Ok(())
        }
    }

    pub fn task_hash(&self) -> String {
        normalized_hash(&self.task)
    }

    pub fn with_checksum(mut self) -> Self {
        self.checksum = Some(self.task_hash());
        self
    }
}

fn is_python_whitespace(character: char) -> bool {
    character.is_whitespace() || matches!(character as u32, 0x1c..=0x1f)
}

fn is_python_word(character: char) -> bool {
    matches!(
        get_general_category(character),
        GeneralCategory::UppercaseLetter
            | GeneralCategory::LowercaseLetter
            | GeneralCategory::TitlecaseLetter
            | GeneralCategory::ModifierLetter
            | GeneralCategory::OtherLetter
            | GeneralCategory::LetterNumber
            | GeneralCategory::DecimalNumber
            | GeneralCategory::OtherNumber
    ) || character == '_'
}

/// Python-compatible `schema.normalized_hash`: lowercase, collapse Unicode
/// whitespace, delete non-word punctuation, SHA-256, then take 16 hex digits.
pub fn normalized_hash(text: &str) -> String {
    let mut compact = String::new();
    let mut pending_space = false;
    for lowered in text.chars().flat_map(char::to_lowercase) {
        if is_python_whitespace(lowered) {
            if !compact.is_empty() {
                pending_space = true;
            }
        } else {
            if pending_space {
                compact.push(' ');
                pending_space = false;
            }
            if is_python_word(lowered) {
                compact.push(lowered);
            }
        }
    }
    let digest = Sha256::digest(compact.as_bytes());
    digest[..8]
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

/// Match `evaluation.sampling.deterministic_sample`, including original-order
/// output and SHA-256 ranking by the exact `"{seed}:{key}"` bytes.
pub fn deterministic_sample<T>(
    items: &[T],
    limit: i64,
    seed: i64,
    key: impl Fn(&T) -> String,
) -> Vec<&T> {
    if limit <= 0 {
        return Vec::new();
    }
    if limit as u128 >= items.len() as u128 {
        return items.iter().collect();
    }
    let mut ranked: Vec<(usize, [u8; 32])> = items
        .iter()
        .enumerate()
        .map(|(index, item)| {
            let input = format!("{seed}:{}", key(item));
            (index, Sha256::digest(input.as_bytes()).into())
        })
        .collect();
    ranked.sort_by_key(|(_, digest)| *digest);
    let mut chosen: Vec<_> = ranked
        .into_iter()
        .take(limit as usize)
        .map(|(index, _)| index)
        .collect();
    chosen.sort_unstable();
    chosen.into_iter().map(|index| &items[index]).collect()
}

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

/// Build the reproducibility metadata returned by Python
/// `evaluation.provenance.environment_snapshot`. Runtime-specific values are
/// supplied by the caller so the contract stays deterministic and testable.
pub fn environment_snapshot(
    agentrouter_version: &str,
    python: &str,
    platform: &str,
    git_sha: Option<&str>,
) -> serde_json::Value {
    serde_json::json!({
        "agentrouter_version": agentrouter_version,
        "python": python,
        "platform": platform,
        "git_sha": git_sha,
    })
}

#[derive(Debug, Clone, Deserialize)]
pub struct AnnotationInputLabel {
    pub annotator: String,
    #[serde(default)]
    pub band: Option<ContextBand>,
    #[serde(default)]
    pub abstain: bool,
    pub rationale: String,
    pub confidence: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AnnotationInputItem {
    pub candidate_id: String,
    pub prompt: String,
    pub category: String,
    #[serde(default)]
    pub labels: Vec<AnnotationInputLabel>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AnnotationAdjudication {
    pub adjudicator: String,
    #[serde(default)]
    pub band: Option<ContextBand>,
    pub abstain: bool,
    pub rationale: String,
    #[serde(default = "default_adjudication_confidence")]
    pub confidence: f64,
}

fn default_adjudication_confidence() -> f64 {
    0.6
}

/// Resolve collected human labels without inventing an answer. A conflicting
/// item remains `None` until an explicit human adjudication is supplied.
pub fn resolve_annotation(
    item: &AnnotationInputItem,
    label_source: &str,
    adjudication: Option<&AnnotationAdjudication>,
) -> Option<serde_json::Value> {
    let unanimous_abstention = !item.labels.is_empty() && item.labels.iter().all(|l| l.abstain);
    let needs_adjudication = annotation_needs_adjudication(item);
    let annotators: Vec<_> = item
        .labels
        .iter()
        .map(|label| label.annotator.clone())
        .collect();

    if !needs_adjudication {
        if unanimous_abstention {
            let confidence = round_half_even(
                item.labels
                    .iter()
                    .map(|label| label.confidence)
                    .sum::<f64>()
                    / item.labels.len() as f64,
                4,
            );
            let rationale = item
                .labels
                .iter()
                .map(|label| label.rationale.as_str())
                .collect::<Vec<_>>()
                .join("; ");
            return Some(annotation_result(
                item,
                label_source,
                annotators,
                AnnotationOutcome {
                    band: None,
                    abstained: true,
                    adjudicated_by: None,
                    rationale,
                    confidence,
                },
            ));
        }
        let matching: Vec<_> = item.labels.iter().filter(|label| !label.abstain).collect();
        let confidence = round_half_even(
            matching.iter().map(|label| label.confidence).sum::<f64>() / matching.len() as f64,
            4,
        );
        let rationale = matching
            .iter()
            .map(|label| label.rationale.as_str())
            .collect::<Vec<_>>()
            .join("; ");
        return Some(annotation_result(
            item,
            label_source,
            annotators,
            AnnotationOutcome {
                band: matching.first().and_then(|label| label.band),
                abstained: false,
                adjudicated_by: None,
                rationale,
                confidence,
            },
        ));
    }

    let decision = adjudication?;
    Some(annotation_result(
        item,
        label_source,
        annotators,
        AnnotationOutcome {
            band: if decision.abstain {
                None
            } else {
                decision.band
            },
            abstained: decision.abstain,
            adjudicated_by: Some(decision.adjudicator.clone()),
            rationale: decision.rationale.clone(),
            confidence: round_half_even(decision.confidence, 4),
        },
    ))
}

pub fn annotation_needs_adjudication(item: &AnnotationInputItem) -> bool {
    if item.labels.len() < 2 {
        return true;
    }
    if item.labels.iter().all(|label| label.abstain) {
        return false;
    }
    let has_abstention = item.labels.iter().any(|label| label.abstain);
    let mut bands = item
        .labels
        .iter()
        .filter(|label| !label.abstain)
        .filter_map(|label| label.band);
    let first = bands.next();
    has_abstention || first.is_none() || bands.any(|band| Some(band) != first)
}

struct AnnotationOutcome {
    band: Option<ContextBand>,
    abstained: bool,
    adjudicated_by: Option<String>,
    rationale: String,
    confidence: f64,
}

fn annotation_result(
    item: &AnnotationInputItem,
    label_source: &str,
    annotators: Vec<String>,
    outcome: AnnotationOutcome,
) -> serde_json::Value {
    serde_json::json!({
        "id": item.candidate_id,
        "prompt": item.prompt,
        "category": item.category,
        "band": outcome.band,
        "abstained": outcome.abstained,
        "label_source": label_source,
        "annotators": annotators,
        "adjudicated_by": outcome.adjudicated_by,
        "rationale": outcome.rationale,
        "confidence": outcome.confidence,
        "split": null,
        "review_status": "pending_human_review",
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
