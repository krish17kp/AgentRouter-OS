//! Legacy classifier gold-set evaluator from `agentrouter/evaluate.py`.
//!
//! This preserves the historical report contract. Canonical release
//! readiness is computed separately by the registered evaluation runner.

use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

use agentrouter_classifier::{classify, ClassifyOptions};
use serde_json::{json, Map, Value};

const DIMENSIONS: [(&str, &str); 6] = [
    ("task_type", "task_type"),
    ("complexity", "complexity"),
    ("risk", "risk"),
    ("output", "output_type"),
    ("context", "context_band"),
    ("approval", "approval"),
];
const WEIGHTS: [(&str, u64); 7] = [
    ("task_type", 10),
    ("risk", 7),
    ("complexity", 4),
    ("tools", 4),
    ("output", 2),
    ("context", 2),
    ("approval", 1),
];

/// Typed loading failures corresponding to the Python evaluator's public
/// `GoldError`, YAML parser, and operating-system error categories.
#[derive(Debug)]
pub enum LegacyGoldError {
    GoldError(String),
    YamlError(String),
    OSError {
        kind: std::io::ErrorKind,
        message: String,
    },
}

impl LegacyGoldError {
    pub fn python_type(&self) -> &'static str {
        match self {
            Self::GoldError(_) => "GoldError",
            Self::YamlError(_) => "YAMLError",
            Self::OSError { kind, .. } => match kind {
                std::io::ErrorKind::NotFound => "FileNotFoundError",
                std::io::ErrorKind::PermissionDenied => "PermissionError",
                std::io::ErrorKind::IsADirectory => "IsADirectoryError",
                std::io::ErrorKind::InvalidData => "UnicodeDecodeError",
                _ => "OSError",
            },
        }
    }
}

impl fmt::Display for LegacyGoldError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::GoldError(message) | Self::YamlError(message) => message,
            Self::OSError { message, .. } => message,
        };
        formatter.write_str(message)
    }
}

impl std::error::Error for LegacyGoldError {}

pub fn load_gold(path: &Path) -> Result<Vec<Value>, LegacyGoldError> {
    if !path.exists() {
        return Err(LegacyGoldError::GoldError(format!(
            "gold benchmark not found: {}",
            path.display()
        )));
    }
    let source = std::fs::read_to_string(path).map_err(|error| LegacyGoldError::OSError {
        kind: error.kind(),
        message: error.to_string(),
    })?;
    let document: Value = serde_yaml::from_str(&source)
        .map_err(|error| LegacyGoldError::YamlError(error.to_string()))?;
    let cases = document
        .get("cases")
        .and_then(Value::as_array)
        .ok_or_else(|| {
            LegacyGoldError::GoldError(format!(
                "{}: expected a mapping with a 'cases' list",
                path.display()
            ))
        })?;
    let mut ids = BTreeSet::new();
    for case in cases {
        let id = case.get("id").cloned().unwrap_or(Value::Null);
        let key = id.to_string();
        if !ids.insert(key) {
            return Err(LegacyGoldError::GoldError(format!(
                "{}: duplicate case ids present",
                path.display()
            )));
        }
    }
    Ok(cases.clone())
}

pub fn evaluate(path: &Path) -> Result<Value, String> {
    let cases = load_gold(path).map_err(|error| error.to_string())?;
    grade_cases(&cases)
}

pub fn load_routing_gold(path: &Path) -> Result<Vec<Value>, String> {
    if !path.exists() {
        return Err(format!("gold benchmark not found: {}", path.display()));
    }
    let source = fs::read_to_string(path).map_err(|error| error.to_string())?;
    let document: Value = serde_yaml::from_str(&source).map_err(|error| error.to_string())?;
    document
        .get("scenarios")
        .and_then(Value::as_array)
        .cloned()
        .ok_or_else(|| {
            format!(
                "{}: expected a mapping with a 'scenarios' list",
                path.display()
            )
        })
}

pub fn evaluate_routing(path: &Path) -> Result<Value, String> {
    grade_routing(&load_routing_gold(path)?)
}

pub fn grade_routing(scenarios: &[Value]) -> Result<Value, String> {
    use agentrouter_registry::{DeprecationStatus, ModelEntry, PricingTier};
    use agentrouter_routing::{route, Weights};

    let mut results = Vec::with_capacity(scenarios.len());
    for scenario in scenarios {
        let scenario_id = scenario.get("id").cloned().unwrap_or(Value::Null);
        let model_values = scenario
            .get("models")
            .and_then(Value::as_array)
            .ok_or_else(|| {
                format!(
                    "scenario {} must include a models list",
                    python_display(&scenario_id)
                )
            })?;
        let mut models = model_values
            .iter()
            .map(|model| {
                serde_json::from_value::<ModelEntry>(model.clone()).map_err(|error| {
                    format!(
                        "scenario {} has invalid model: {error}",
                        python_display(&scenario_id)
                    )
                })
            })
            .collect::<Result<Vec<_>, _>>()?;
        let by_id: BTreeMap<_, _> = models
            .iter()
            .map(|model| (model.model_id.clone(), model.clone()))
            .collect();
        let cap = scenario
            .get("max_pricing_tier")
            .and_then(Value::as_str)
            .map(|value| {
                serde_json::from_value::<PricingTier>(json!(value))
                    .map_err(|error| format!("invalid max_pricing_tier: {error}"))
            })
            .transpose()?;
        if let Some(cap) = cap {
            models.retain(|model| pricing_rank(model.pricing_tier) <= pricing_rank(cap));
        }
        let cls = scenario_classification(scenario.get("classification"))?;
        let route_result = route(&models, &cls, Weights::default(), None);
        let recommendation = route_result
            .recommendation
            .as_ref()
            .map(|model| model.model_id.as_str());
        let fallback = route_result
            .fallback
            .as_ref()
            .map(|model| model.model_id.as_str());
        let excluded_ids: BTreeSet<_> = route_result
            .excluded
            .iter()
            .map(|excluded| {
                excluded
                    .model
                    .split_once('/')
                    .map_or(excluded.model.as_str(), |(_, id)| id)
                    .to_owned()
            })
            .collect();
        let expected = scenario.get("expect").cloned().unwrap_or_else(|| json!({}));
        let mut checks = Map::new();
        if let Some(value) = expected.get("recommendation") {
            let wanted = value.as_str().unwrap_or_default();
            checks.insert(
                "recommendation".to_owned(),
                json!(recommendation == Some(wanted)),
            );
        }
        if let Some(value) = expected.get("fallback") {
            let acceptable: Vec<_> = value
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(Value::as_str)
                .collect();
            checks.insert(
                "fallback".to_owned(),
                json!(fallback.map_or(acceptable.is_empty(), |actual| acceptable.contains(&actual))),
            );
        }
        if let Some(value) = expected.get("excluded") {
            let all_excluded = value
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(Value::as_str)
                .all(|model_id| excluded_ids.contains(model_id));
            checks.insert("excluded".to_owned(), json!(all_excluded));
        }
        if expected.get("no_eligible").and_then(Value::as_bool) == Some(true) {
            checks.insert("no_eligible".to_owned(), json!(recommendation.is_none()));
        }
        if let Some(cap) = cap {
            let within_cap = recommendation.is_none_or(|model_id| {
                by_id
                    .get(model_id)
                    .is_some_and(|model| pricing_rank(model.pricing_tier) <= pricing_rank(cap))
            });
            checks.insert("pricing_cap".to_owned(), json!(within_cap));
        }
        if let Some(model_id) = recommendation {
            let not_retired = by_id
                .get(model_id)
                .is_some_and(|model| model.deprecation_status != DeprecationStatus::Retired);
            checks.insert("no_retired_win".to_owned(), json!(not_retired));
        }
        let ok = checks.values().all(|check| check.as_bool() == Some(true));
        results.push(json!({
            "id": scenario_id,
            "description": scenario.get("description").and_then(Value::as_str).unwrap_or_default(),
            "checks": checks,
            "ok": ok,
        }));
    }
    let passed = results.iter().filter(|result| result["ok"] == true).count();
    let failures: Vec<_> = results
        .iter()
        .filter(|result| result["ok"] == false)
        .cloned()
        .collect();
    Ok(json!({
        "n_scenarios": results.len(),
        "passed": passed,
        "all_pass": passed == results.len(),
        "scenarios": results,
        "failures": failures,
    }))
}

fn scenario_classification(
    value: Option<&Value>,
) -> Result<agentrouter_core::Classification, String> {
    let value = value.cloned().unwrap_or_else(|| json!({}));
    let task_type = value
        .get("task_type")
        .and_then(Value::as_str)
        .unwrap_or("coding");
    let complexity = value
        .get("complexity")
        .and_then(Value::as_str)
        .unwrap_or("medium");
    let risk = value.get("risk").and_then(Value::as_str).unwrap_or("low");
    let context_tokens = value
        .get("context_tokens")
        .and_then(Value::as_u64)
        .unwrap_or(4_000);
    let context_band = value
        .get("context_band")
        .and_then(Value::as_str)
        .map(str::to_owned)
        .unwrap_or_else(|| {
            if context_tokens < 8_000 {
                "small".to_owned()
            } else if context_tokens < 64_000 {
                "medium".to_owned()
            } else {
                "large".to_owned()
            }
        });
    let approval_level = value
        .get("approval_level")
        .and_then(Value::as_str)
        .map(str::to_owned)
        .unwrap_or_else(|| match risk {
            "low" => "auto".to_owned(),
            "medium" => "notify".to_owned(),
            _ => "human-approval-required".to_owned(),
        });
    let classification = json!({
        "task_type": task_type,
        "complexity": complexity,
        "risk": risk,
        "context_tokens": context_tokens,
        "context_band": context_band,
        "output_type": value.get("output_type").and_then(Value::as_str).unwrap_or("code"),
        "tool_needs": value.get("tool_needs").cloned().unwrap_or_else(|| json!([])),
        "approval_level": approval_level,
    });
    serde_json::from_value::<agentrouter_core::Classification>(classification)
        .map_err(|error| format!("invalid scenario classification: {error}"))
}

fn pricing_rank(tier: agentrouter_registry::PricingTier) -> u8 {
    use agentrouter_registry::PricingTier::{Free, Frontier, High, Low, Medium};
    match tier {
        Free => 0,
        Low => 1,
        Medium => 2,
        High => 3,
        Frontier => 4,
    }
}

pub fn write_artifacts(report: &Value, out_dir: &Path) -> Result<Vec<PathBuf>, String> {
    fs::create_dir_all(out_dir).map_err(|error| error.to_string())?;
    let json_path = out_dir.join("evaluation.json");
    let markdown_path = out_dir.join("evaluation.md");
    let csv_path = out_dir.join("failures.csv");
    let mut slim = report.clone();
    if let Some(object) = slim.as_object_mut() {
        object.remove("cases");
    }
    fs::write(&json_path, python_json_dumps_pretty(&slim)?).map_err(|error| error.to_string())?;
    fs::write(&markdown_path, render_markdown(report)).map_err(|error| error.to_string())?;
    fs::write(&csv_path, render_failures_csv(report)).map_err(|error| error.to_string())?;
    Ok(vec![json_path, markdown_path, csv_path])
}

fn python_json_dumps_pretty(value: &Value) -> Result<String, String> {
    let encoded = serde_json::to_string_pretty(value).map_err(|error| error.to_string())?;
    let mut output = String::with_capacity(encoded.len());
    let mut in_string = false;
    let mut escaped = false;
    for character in encoded.chars() {
        if in_string && !escaped && character as u32 > 0x7f {
            let codepoint = character as u32;
            if codepoint <= 0xffff {
                use fmt::Write as _;
                write!(output, "\\u{codepoint:04x}").map_err(|error| error.to_string())?;
            } else {
                let adjusted = codepoint - 0x1_0000;
                let high = 0xd800 + (adjusted >> 10);
                let low = 0xdc00 + (adjusted & 0x3ff);
                use fmt::Write as _;
                write!(output, "\\u{high:04x}\\u{low:04x}").map_err(|error| error.to_string())?;
            }
            continue;
        }
        output.push(character);
        if in_string {
            if escaped {
                escaped = false;
            } else if character == '\\' {
                escaped = true;
            } else if character == '"' {
                in_string = false;
            }
        } else if character == '"' {
            in_string = true;
        }
    }
    Ok(output)
}

pub fn render_markdown(report: &Value) -> String {
    let mut lines = vec![
        "# Classifier Evaluation Report".to_owned(),
        String::new(),
        format!("- Cases: **{}**", report["n_cases"]),
        format!("- Overall grade: **{} / 100**", report["overall_grade"]),
        format!(
            "- Release-ready: **{}**",
            if report["release_ready"] == true {
                "YES"
            } else {
                "NO"
            }
        ),
        String::new(),
        "## Dimension scores (weighted into the grade)".to_owned(),
        String::new(),
        "| Dimension | Weight | Score | Accuracy | Macro F1 |".to_owned(),
        "|---|---|---|---|---|".to_owned(),
    ];
    for (dimension, weight) in WEIGHTS {
        let accuracy = if dimension == "tools" {
            report["tools"]["f1"].clone()
        } else {
            report[dimension]["accuracy"].clone()
        };
        let macro_f1 = if matches!(dimension, "task_type" | "risk" | "complexity") {
            python_number(&report[dimension]["macro_f1"])
        } else {
            "-".to_owned()
        };
        lines.push(format!(
            "| {dimension} | {weight} | {} | {} | {macro_f1} |",
            report["dimension_scores"][dimension], accuracy
        ));
    }
    lines.extend([
        String::new(),
        "## Key metrics".to_owned(),
        String::new(),
        format!(
            "- Task-type macro F1: **{}**",
            python_display(&report["task_type"]["macro_f1"])
        ),
        format!(
            "- High-risk recall: **{}**",
            python_repr(&report["risk"]["high_risk_recall"])
        ),
        format!(
            "- Risk per-class recall: {}",
            python_repr(&report["risk"]["per_class_recall"])
        ),
        format!(
            "- Tool precision / recall / F1: {} / {} / {}",
            report["tools"]["precision"], report["tools"]["recall"], report["tools"]["f1"]
        ),
        format!(
            "- Approval accuracy: **{}**",
            python_display(&report["approval"]["accuracy"])
        ),
        String::new(),
        "## Release thresholds".to_owned(),
        String::new(),
        "| Threshold | Met |".to_owned(),
        "|---|---|".to_owned(),
    ]);
    if let Some(thresholds) = report["release_thresholds"].as_object() {
        for (name, met) in thresholds {
            lines.push(format!(
                "| {name} | {} |",
                if met == true { "PASS" } else { "FAIL" }
            ));
        }
    }
    let failures = report["failures"].as_array().map_or(&[][..], Vec::as_slice);
    lines.extend([
        String::new(),
        format!("## Failed cases ({})", failures.len()),
        String::new(),
    ]);
    if failures.is_empty() {
        lines.push("_None._".to_owned());
    } else {
        lines.extend([
            "| id | prompt | failed dimensions |".to_owned(),
            "|---|---|---|".to_owned(),
        ]);
        for case in failures {
            let dims = case["failed"]
                .as_array()
                .into_iter()
                .flatten()
                .map(|failure| {
                    format!(
                        "{}(exp {} got {})",
                        failure["dim"].as_str().unwrap_or_default(),
                        python_repr(&failure["expected"]),
                        python_display(&failure["predicted"])
                    )
                })
                .collect::<Vec<_>>()
                .join(", ");
            let prompt = case["prompt"]
                .as_str()
                .unwrap_or_default()
                .replace('|', "\\|");
            lines.push(format!(
                "| {} | {prompt} | {dims} |",
                python_display(&case["id"])
            ));
        }
    }
    format!("{}\n", lines.join("\n"))
}

fn render_failures_csv(report: &Value) -> String {
    let mut csv = String::from("id,prompt,dimension,expected,predicted\r\n");
    for case in report["failures"].as_array().into_iter().flatten() {
        let id = case["id"].as_str().unwrap_or_default();
        let prompt = case["prompt"].as_str().unwrap_or_default();
        for failure in case["failed"].as_array().into_iter().flatten() {
            let expected = failure["expected"]
                .as_array()
                .into_iter()
                .flatten()
                .map(csv_cell_value)
                .collect::<Vec<_>>()
                .join("|");
            let predicted = match &failure["predicted"] {
                Value::Array(values) => values
                    .iter()
                    .map(csv_cell_value)
                    .collect::<Vec<_>>()
                    .join("|"),
                value => csv_cell_value(value),
            };
            for field in [
                id.to_owned(),
                prompt.to_owned(),
                failure["dim"].as_str().unwrap_or_default().to_owned(),
                expected,
                predicted,
            ] {
                csv.push_str(&csv_escape(&field));
                csv.push(',');
            }
            csv.pop();
            csv.push_str("\r\n");
        }
    }
    csv
}

fn csv_cell_value(value: &Value) -> String {
    match value {
        Value::String(value) => value.clone(),
        Value::Null => String::new(),
        other => other.to_string(),
    }
}

fn csv_escape(value: &str) -> String {
    if value.contains([',', '"', '\r', '\n']) {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.to_owned()
    }
}

fn python_number(value: &Value) -> String {
    python_repr(value)
}

fn python_display(value: &Value) -> String {
    match value {
        Value::String(value) => value.clone(),
        _ => python_repr(value),
    }
}

fn python_repr(value: &Value) -> String {
    match value {
        Value::Null => "None".to_owned(),
        Value::Bool(true) => "True".to_owned(),
        Value::Bool(false) => "False".to_owned(),
        Value::Number(number) => number.to_string(),
        Value::String(string) => {
            let quote = if string.contains('\'') && !string.contains('"') {
                '"'
            } else {
                '\''
            };
            let mut escaped = String::new();
            for character in string.chars() {
                match character {
                    '\\' => escaped.push_str("\\\\"),
                    '\n' => escaped.push_str("\\n"),
                    '\r' => escaped.push_str("\\r"),
                    '\t' => escaped.push_str("\\t"),
                    value if value == quote => {
                        escaped.push('\\');
                        escaped.push(value);
                    }
                    value => escaped.push(value),
                }
            }
            format!("{quote}{escaped}{quote}")
        }
        Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(python_repr)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(values) => format!(
            "{{{}}}",
            values
                .iter()
                .map(|(key, value)| format!("{}: {}", python_repr(&json!(key)), python_repr(value)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}

pub fn grade_cases(cases: &[Value]) -> Result<Value, String> {
    grade_cases_with(cases, |prompt| {
        classify(prompt, &ClassifyOptions::default())
    })
}

pub fn grade_cases_with<F>(cases: &[Value], classify_fn: F) -> Result<Value, String>
where
    F: Fn(&str) -> agentrouter_core::Classification,
{
    let mut single: BTreeMap<&str, Vec<(Vec<Value>, String)>> = DIMENSIONS
        .iter()
        .map(|(dimension, _)| (*dimension, Vec::new()))
        .collect();
    let mut tools_pairs = Vec::new();
    let mut per_case = Vec::with_capacity(cases.len());

    for case in cases {
        let prompt = case
            .get("prompt")
            .and_then(Value::as_str)
            .ok_or_else(|| "each gold case must include a string prompt".to_owned())?;
        let raw_prediction =
            serde_json::to_value(classify_fn(prompt)).map_err(|error| error.to_string())?;
        let mut predicted = Map::new();
        let mut failed = Vec::new();

        for (dimension, gold_field) in DIMENSIONS {
            let labels = if dimension == "approval" {
                approval_labels(case.get("risk"))?
            } else {
                labels(case.get(gold_field))
            };
            let pred_field = match dimension {
                "output" => "output_type",
                "context" => "context_band",
                "approval" => "approval_level",
                other => other,
            };
            let prediction = raw_prediction
                .get(pred_field)
                .and_then(Value::as_str)
                .ok_or_else(|| format!("classifier returned invalid {pred_field}"))?
                .to_owned();
            predicted.insert(dimension.to_owned(), json!(prediction));
            if !labels.is_empty() {
                single
                    .entry(dimension)
                    .or_default()
                    .push((labels.clone(), prediction.clone()));
                if !labels.contains(&Value::String(prediction.clone())) {
                    failed.push(json!({
                        "dim": dimension,
                        "expected": labels,
                        "predicted": prediction,
                    }));
                }
            }
        }

        let predicted_tools = sorted_strings(raw_prediction["tool_needs"].as_array());
        predicted.insert("tools".to_owned(), json!(predicted_tools));
        if let Some(expected) = case.get("tools") {
            let expected_tools = sorted_strings(expected.as_array());
            tools_pairs.push((expected_tools.clone(), predicted["tools"].clone()));
            if expected_tools != predicted["tools"] {
                failed.push(json!({
                    "dim": "tools",
                    "expected": expected_tools,
                    "predicted": predicted["tools"],
                }));
            }
        }

        per_case.push(json!({
            "id": case.get("id").cloned().unwrap_or(Value::Null),
            "prompt": prompt,
            "predicted": predicted,
            "failed": failed,
            "ok": failed.is_empty(),
        }));
    }

    let mut metrics = Map::new();
    for (dimension, _) in DIMENSIONS {
        metrics.insert(dimension.to_owned(), score_single(&single[dimension]));
    }
    let tools = score_tools(&tools_pairs);
    let mut dimension_scores = Map::new();
    let mut grade_weights = Map::new();
    let mut weighted = 0.0;
    for (dimension, weight) in WEIGHTS {
        let score = if dimension == "tools" {
            tools["f1"].as_f64().unwrap_or(0.0)
        } else {
            metrics[dimension]["accuracy"].as_f64().unwrap_or(0.0)
        };
        dimension_scores.insert(dimension.to_owned(), json!(round_to(score, 4)));
        grade_weights.insert(dimension.to_owned(), json!(weight));
        weighted += weight as f64 * score;
    }
    let overall = round_to(100.0 * weighted / 30.0, 2);
    let risk = &metrics["risk"];
    let high_risk_recall = risk["per_class_recall"]
        .get("high")
        .cloned()
        .unwrap_or(Value::Null);
    let mut risk_report = risk.clone();
    risk_report["high_risk_recall"] = high_risk_recall.clone();
    let thresholds = json!({
        "overall_grade>=85": overall >= 85.0,
        "task_type_macro_f1>=0.90": metrics["task_type"]["macro_f1"].as_f64().unwrap_or(0.0) >= 0.90,
        "high_risk_recall==1.00": high_risk_recall.as_f64() == Some(1.0),
        "approval_accuracy==1.00": metrics["approval"]["accuracy"].as_f64() == Some(1.0),
        "tool_f1>=0.90": tools["f1"].as_f64().unwrap_or(0.0) >= 0.90,
    });
    let release_ready = thresholds
        .as_object()
        .is_some_and(|values| values.values().all(|value| value.as_bool() == Some(true)));

    let report = json!({
        "n_cases": cases.len(),
        "overall_grade": overall,
        "dimension_scores": dimension_scores,
        "grade_weights": grade_weights,
        "task_type": metrics["task_type"],
        "complexity": metrics["complexity"],
        "risk": risk_report,
        "tools": tools,
        "context": metrics["context"],
        "output": metrics["output"],
        "approval": metrics["approval"],
        "release_thresholds": thresholds,
        "release_ready": release_ready,
        "readiness_scope": "legacy_gold_set_only",
        "canonical_release_ready": null,
        "failures": per_case.iter().filter(|case| case["ok"] == false).cloned().collect::<Vec<_>>(),
        "cases": per_case,
    });
    Ok(report)
}

fn labels(value: Option<&Value>) -> Vec<Value> {
    match value {
        None | Some(Value::Null) => Vec::new(),
        Some(Value::Array(values)) => values.clone(),
        Some(value) => vec![value.clone()],
    }
}

fn approval_labels(risks: Option<&Value>) -> Result<Vec<Value>, String> {
    let mut approvals = BTreeSet::new();
    for risk in labels(risks) {
        let value = match risk.as_str() {
            Some("low") => "auto",
            Some("medium") => "notify",
            Some("high") => "human-approval-required",
            Some(other) => return Err(format!("unknown risk label '{other}'")),
            None => return Err("risk labels must be strings".to_owned()),
        };
        approvals.insert(value.to_owned());
    }
    Ok(approvals.into_iter().map(Value::String).collect())
}

fn sorted_strings(values: Option<&Vec<Value>>) -> Value {
    let mut strings: Vec<_> = values
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(str::to_owned)
        .collect();
    strings.sort();
    strings.dedup();
    json!(strings)
}

fn score_single(pairs: &[(Vec<Value>, String)]) -> Value {
    let mut tp: BTreeMap<String, usize> = BTreeMap::new();
    let mut fp: BTreeMap<String, usize> = BTreeMap::new();
    let mut misses: BTreeMap<String, usize> = BTreeMap::new();
    let mut correct = 0usize;
    for (acceptable, prediction) in pairs {
        if acceptable.contains(&json!(prediction)) {
            correct += 1;
            *tp.entry(prediction.clone()).or_default() += 1;
        } else if let Some(canonical) = acceptable.first().and_then(Value::as_str) {
            *misses.entry(canonical.to_owned()).or_default() += 1;
            *fp.entry(prediction.clone()).or_default() += 1;
        }
    }
    let classes: BTreeSet<_> = tp
        .keys()
        .chain(fp.keys())
        .chain(misses.keys())
        .cloned()
        .collect();
    let mut f1s = Vec::new();
    let mut recalls = Map::new();
    for class in classes {
        let true_positive = *tp.get(&class).unwrap_or(&0) as f64;
        let false_positive = *fp.get(&class).unwrap_or(&0) as f64;
        let false_negative = *misses.get(&class).unwrap_or(&0) as f64;
        let precision = if true_positive + false_positive > 0.0 {
            true_positive / (true_positive + false_positive)
        } else {
            0.0
        };
        let recall = if true_positive + false_negative > 0.0 {
            true_positive / (true_positive + false_negative)
        } else {
            0.0
        };
        f1s.push(if precision + recall > 0.0 {
            2.0 * precision * recall / (precision + recall)
        } else {
            0.0
        });
        if true_positive + false_negative > 0.0 {
            recalls.insert(class, json!(round_to(recall, 4)));
        }
    }
    let accuracy = if pairs.is_empty() {
        0.0
    } else {
        correct as f64 / pairs.len() as f64
    };
    let macro_f1 = if f1s.is_empty() {
        0.0
    } else {
        f1s.iter().sum::<f64>() / f1s.len() as f64
    };
    json!({
        "accuracy": round_to(accuracy, 4),
        "macro_f1": round_to(macro_f1, 4),
        "per_class_recall": recalls,
        "n": pairs.len(),
    })
}

fn score_tools(pairs: &[(Value, Value)]) -> Value {
    let (mut tp, mut fp, mut misses, mut exact) = (0usize, 0usize, 0usize, 0usize);
    for (expected, predicted) in pairs {
        let expected: BTreeSet<_> = expected
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
            .map(str::to_owned)
            .collect();
        let predicted: BTreeSet<_> = predicted
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
            .map(str::to_owned)
            .collect();
        tp += expected.intersection(&predicted).count();
        fp += predicted.difference(&expected).count();
        misses += expected.difference(&predicted).count();
        exact += usize::from(expected == predicted);
    }
    let precision = if tp + fp == 0 {
        1.0
    } else {
        tp as f64 / (tp + fp) as f64
    };
    let recall = if tp + misses == 0 {
        1.0
    } else {
        tp as f64 / (tp + misses) as f64
    };
    let f1 = if precision + recall == 0.0 {
        0.0
    } else {
        2.0 * precision * recall / (precision + recall)
    };
    json!({
        "precision": round_to(precision, 4),
        "recall": round_to(recall, 4),
        "f1": round_to(f1, 4),
        "exact_set_accuracy": if pairs.is_empty() { 0.0 } else { round_to(exact as f64 / pairs.len() as f64, 4) },
        "n": pairs.len(),
    })
}

fn round_to(value: f64, places: i32) -> f64 {
    super::round_to(value, places)
}

#[cfg(test)]
mod tests {
    use super::*;
    use agentrouter_core::{ApprovalLevel, ContextBand, Level, OutputType, TaskType};

    #[test]
    fn injected_classifier_matches_the_python_grade_cases_contract() {
        let cases = vec![json!({
            "id": "gold",
            "prompt": "fixture prompt",
            "task_type": ["coding"],
            "complexity": ["high"],
            "risk": ["high"],
            "output_type": ["code+tests"],
            "context_band": ["medium"],
            "tools": ["file-edit", "shell"],
        })];
        let prediction = agentrouter_core::Classification {
            task_type: TaskType::Coding,
            complexity: Level::High,
            risk: Level::High,
            context_tokens: 4_000,
            context_band: ContextBand::Medium,
            output_type: OutputType::CodeTests,
            tool_needs: vec!["file-edit".to_owned(), "shell".to_owned()],
            approval_level: ApprovalLevel::HumanApprovalRequired,
            confidence: 1.0,
            needs_clarification: false,
            alternative_task_type: None,
            ambiguity_reason: None,
        };
        let report = grade_cases_with(&cases, |_| prediction.clone()).unwrap();
        assert_eq!(report["overall_grade"], 100.0);
        assert_eq!(report["failures"], json!([]));
        assert_eq!(report["release_thresholds"]["high_risk_recall==1.00"], true);
    }
}
