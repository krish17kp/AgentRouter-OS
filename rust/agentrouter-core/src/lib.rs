//! Shared types for AgentRouter OS. Ports the enums and value types from
//! `agentrouter/schema.py` that downstream crates (classifier, registry,
//! routing, ...) all need, with no routing/classification logic here.
//!
//! Serde string values match the Python `str, Enum` values exactly (e.g.
//! `"code+tests"`, `"human-approval-required"`) so JSON produced by either
//! implementation round-trips through the other — this is the contract the
//! Python/Rust compatibility tests in `tests/` check.

use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskType {
    Coding,
    Reasoning,
    Writing,
    Analysis,
    Summarization,
    General,
}

/// Shared by complexity and risk per `schema.py`'s comment: "low/medium/high".
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Level {
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OutputType {
    #[serde(rename = "code")]
    Code,
    #[serde(rename = "text")]
    Text,
    #[serde(rename = "code+tests")]
    CodeTests,
    #[serde(rename = "data")]
    Data,
    #[serde(rename = "plan")]
    Plan,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ApprovalLevel {
    #[serde(rename = "auto")]
    Auto,
    #[serde(rename = "notify")]
    Notify,
    #[serde(rename = "human-approval-required")]
    HumanApprovalRequired,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContextBand {
    Small,
    Medium,
    Large,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PricingTier {
    Free,
    Low,
    Medium,
    High,
    Frontier,
}

/// The result of classifying a task — mirrors `schema.Classification`'s 7
/// canonical dimensions (ROUTING_RULES.md §1) plus the P3 confidence fields.
/// Field names match the Python model exactly (`approval_level`, not
/// `approval`) since this is the JSON contract the compatibility test checks.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Classification {
    pub task_type: TaskType,
    pub complexity: Level,
    pub risk: Level,
    pub context_tokens: u32,
    pub context_band: ContextBand,
    pub output_type: OutputType,
    pub tool_needs: Vec<String>,
    pub approval_level: ApprovalLevel,
    #[serde(default = "default_confidence")]
    pub confidence: f64,
    #[serde(default)]
    pub needs_clarification: bool,
    // No `skip_serializing_if`: Pydantic's default `model_dump_json()` always
    // emits `None` fields as JSON `null` rather than omitting the key, so we
    // match that instead of omitting — this is what the compatibility test
    // in `tests/test_rust_compat.py` checks byte-for-byte.
    #[serde(default)]
    pub alternative_task_type: Option<TaskType>,
    #[serde(default)]
    pub ambiguity_reason: Option<String>,
}

fn default_confidence() -> f64 {
    1.0
}

/// Errors shared across crates. Downstream crates extend this via
/// `#[from]`/wrapping rather than inventing parallel error enums, matching
/// the "fail closed on unknown controls, malformed registries" invariant in
/// `AGENTS.md`.
#[derive(Debug, Error)]
pub enum CoreError {
    #[error("invalid enum value {value:?} for {field}")]
    InvalidEnumValue { field: &'static str, value: String },
    #[error("serialization failed: {0}")]
    Serde(#[from] serde_json::Error),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn output_type_matches_python_string_values() {
        assert_eq!(
            serde_json::to_string(&OutputType::CodeTests).unwrap(),
            r#""code+tests""#
        );
        assert_eq!(
            serde_json::to_string(&ApprovalLevel::HumanApprovalRequired).unwrap(),
            r#""human-approval-required""#
        );
    }

    #[test]
    fn level_round_trips_and_orders_low_to_high() {
        assert!(Level::Low < Level::Medium);
        assert!(Level::Medium < Level::High);
        let json = serde_json::to_string(&Level::High).unwrap();
        assert_eq!(json, r#""high""#);
        let back: Level = serde_json::from_str(&json).unwrap();
        assert_eq!(back, Level::High);
    }

    #[test]
    fn task_type_rejects_unknown_variant() {
        let err = serde_json::from_str::<TaskType>(r#""not-a-real-type""#).unwrap_err();
        assert!(err.to_string().contains("unknown variant"));
    }

    #[test]
    fn classification_round_trips_through_json() {
        let c = Classification {
            task_type: TaskType::Coding,
            complexity: Level::Medium,
            risk: Level::Low,
            context_tokens: 0,
            context_band: ContextBand::Small,
            output_type: OutputType::CodeTests,
            tool_needs: vec![],
            approval_level: ApprovalLevel::Notify,
            confidence: 1.0,
            needs_clarification: false,
            alternative_task_type: None,
            ambiguity_reason: None,
        };
        let json = serde_json::to_string(&c).unwrap();
        let back: Classification = serde_json::from_str(&json).unwrap();
        assert_eq!(back.task_type, TaskType::Coding);
        assert_eq!(back.output_type, OutputType::CodeTests);
    }
}
