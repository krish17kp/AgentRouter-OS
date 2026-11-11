//! Pure evaluation metric aggregation, ported from
//! `agentrouter/evaluation/metrics.py`.
//!
//! Predictions are supplied by the caller so the scorer can be differentially
//! checked offline without running a model or changing evaluation labels.

use std::collections::{BTreeMap, BTreeSet};

use agentrouter_core::{ApprovalLevel, ContextBand, Level, OutputType, PricingTier, TaskType};
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
    let class_score = round_to(weighted_score / 30.0, 4);

    let mut dimensions = Map::new();
    for (dimension, weight) in GRADE_DIMENSIONS {
        let entry = if dimension == "classification" {
            json!({
                "weight": weight,
                "status": "measured",
                "score": class_score,
                "achieved": round_to(weight as f64 * class_score, 3),
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

fn round_to(value: f64, decimal_places: i32) -> f64 {
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
