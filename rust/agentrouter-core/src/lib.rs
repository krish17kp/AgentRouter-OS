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

const PROJECT_METADATA: &str = include_str!("../../../pyproject.toml");

/// The distribution version shared with the Python package metadata.
pub fn package_version() -> &'static str {
    PROJECT_METADATA
        .lines()
        .find_map(|line| {
            line.strip_prefix("version = \"")
                .and_then(|value| value.strip_suffix('\"'))
        })
        .expect("pyproject.toml must declare the AgentRouter distribution version")
}

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
#[serde(deny_unknown_fields)]
pub struct Classification {
    pub task_type: TaskType,
    pub complexity: Level,
    pub risk: Level,
    pub context_tokens: u32,
    pub context_band: ContextBand,
    pub output_type: OutputType,
    pub tool_needs: Vec<String>,
    pub approval_level: ApprovalLevel,
    #[serde(
        default = "default_confidence",
        deserialize_with = "deserialize_pydantic_confidence"
    )]
    pub confidence: f64,
    #[serde(default, deserialize_with = "deserialize_pydantic_bool")]
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

#[derive(Debug)]
enum PydanticScalar {
    Bool(bool),
    Signed(i64),
    Unsigned(u64),
    Float(f64),
    Text(String),
}

struct PydanticScalarVisitor;

impl<'de> serde::de::Visitor<'de> for PydanticScalarVisitor {
    type Value = PydanticScalar;

    fn expecting(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("a Pydantic-compatible scalar")
    }

    fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Bool(value))
    }

    fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Signed(value))
    }

    fn visit_i128<E>(self, value: i128) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        i64::try_from(value)
            .map(PydanticScalar::Signed)
            .or_else(|_| Ok(PydanticScalar::Text(value.to_string())))
    }

    fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Unsigned(value))
    }

    fn visit_u128<E>(self, value: u128) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        u64::try_from(value)
            .map(PydanticScalar::Unsigned)
            .or_else(|_| Ok(PydanticScalar::Text(value.to_string())))
    }

    fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Float(value))
    }

    fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Text(value.to_owned()))
    }

    fn visit_string<E>(self, value: String) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Text(value))
    }

    fn visit_map<M>(self, mut map: M) -> Result<Self::Value, M::Error>
    where
        M: serde::de::MapAccess<'de>,
    {
        // serde_json's arbitrary_precision feature streams number tokens to
        // scalar visitors using this private one-entry map representation.
        let key = map.next_key::<String>()?;
        if key.as_deref() != Some("$serde_json::private::Number") {
            return Err(serde::de::Error::custom("expected a scalar value"));
        }
        let number = map.next_value::<String>()?;
        if map.next_key::<serde::de::IgnoredAny>()?.is_some() {
            return Err(serde::de::Error::custom("expected one scalar value"));
        }
        Ok(parse_json_number_text(number))
    }
}

impl<'de> Deserialize<'de> for PydanticScalar {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        deserializer.deserialize_any(PydanticScalarVisitor)
    }
}

fn parse_json_number_text(value: String) -> PydanticScalar {
    if let Ok(value) = value.parse::<i64>() {
        return PydanticScalar::Signed(value);
    }
    if let Ok(value) = value.parse::<u64>() {
        return PydanticScalar::Unsigned(value);
    }
    if let Ok(value) = value.parse::<f64>() {
        return PydanticScalar::Float(value);
    }
    PydanticScalar::Text(value)
}

fn strip_valid_digit_separators(value: &str) -> Option<String> {
    let characters: Vec<char> = value.chars().collect();
    let mut normalized = String::with_capacity(value.len());
    for (index, character) in characters.iter().copied().enumerate() {
        if character == '_' {
            if !characters
                .get(index.wrapping_sub(1))
                .is_some_and(|previous| previous.is_ascii_digit())
                || !characters
                    .get(index + 1)
                    .is_some_and(|next| next.is_ascii_digit())
            {
                return None;
            }
        } else {
            normalized.push(character);
        }
    }
    Some(normalized)
}

fn parse_pydantic_float(value: PydanticScalar) -> Option<f64> {
    match value {
        PydanticScalar::Bool(value) => Some(if value { 1.0 } else { 0.0 }),
        PydanticScalar::Signed(value) => Some(value as f64),
        PydanticScalar::Unsigned(value) => Some(value as f64),
        PydanticScalar::Float(value) => Some(value),
        PydanticScalar::Text(value) => {
            let normalized = if value.contains('_') {
                strip_valid_digit_separators(&value)?
            } else {
                value.trim().to_owned()
            };
            normalized.parse::<f64>().ok()
        }
    }
}

fn parse_pydantic_bool(value: PydanticScalar) -> Option<bool> {
    match value {
        PydanticScalar::Bool(value) => Some(value),
        PydanticScalar::Signed(0) | PydanticScalar::Unsigned(0) => Some(false),
        PydanticScalar::Signed(1) | PydanticScalar::Unsigned(1) => Some(true),
        PydanticScalar::Float(0.0) => Some(false),
        PydanticScalar::Float(1.0) => Some(true),
        PydanticScalar::Text(value) => match value.to_ascii_lowercase().as_str() {
            "0" | "false" | "off" | "no" | "n" | "f" => Some(false),
            "1" | "true" | "on" | "yes" | "y" | "t" => Some(true),
            _ => None,
        },
        _ => None,
    }
}

fn deserialize_pydantic_confidence<'de, D>(deserializer: D) -> Result<f64, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = parse_pydantic_float(PydanticScalar::deserialize(deserializer)?)
        .filter(|value| value.is_finite() && (0.0..=1.0).contains(value))
        .ok_or_else(|| serde::de::Error::custom("confidence must be between 0 and 1"))?;
    Ok(value)
}

fn deserialize_pydantic_bool<'de, D>(deserializer: D) -> Result<bool, D::Error>
where
    D: serde::Deserializer<'de>,
{
    parse_pydantic_bool(PydanticScalar::deserialize(deserializer)?)
        .ok_or_else(|| serde::de::Error::custom("invalid boolean value"))
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

    #[test]
    fn classification_rejects_unknown_fields_like_python() {
        let mut value = serde_json::json!({
            "task_type": "coding",
            "complexity": "medium",
            "risk": "low",
            "context_tokens": 12,
            "context_band": "small",
            "output_type": "code",
            "tool_needs": [],
            "approval_level": "auto",
            "unexpected": true
        });
        assert!(serde_json::from_value::<Classification>(value.clone()).is_err());
        value.as_object_mut().unwrap().remove("unexpected");
        assert!(serde_json::from_value::<Classification>(value).is_ok());
    }

    fn classification_with_scalars(confidence: &str, needs_clarification: &str) -> String {
        format!(
            r#"{{
                "task_type":"coding",
                "complexity":"medium",
                "risk":"low",
                "context_tokens":12,
                "context_band":"small",
                "output_type":"code",
                "tool_needs":[],
                "approval_level":"auto",
                "confidence":{confidence},
                "needs_clarification":{needs_clarification}
            }}"#
        )
    }

    #[test]
    fn classification_matches_pydantic_confidence_and_boolean_coercions() {
        let cases = [
            ("0.4", "false", 0.4, false),
            ("\"0.5\"", "\"yes\"", 0.5, true),
            ("true", "0", 1.0, false),
            ("false", "1.0", 0.0, true),
            ("\"0.0_5\"", "\"off\"", 0.05, false),
            ("\" 0.5 \"", "\"no\"", 0.5, false),
            ("-0.0", "-0.0", -0.0, false),
        ];
        for (confidence, needs_clarification, expected_confidence, expected_bool) in cases {
            let json = classification_with_scalars(confidence, needs_clarification);
            let classification: Classification = serde_json::from_str(&json).unwrap();
            assert_eq!(classification.confidence, expected_confidence);
            assert_eq!(classification.needs_clarification, expected_bool);
        }
    }

    #[test]
    fn classification_rejects_invalid_pydantic_confidence_and_boolean_values() {
        for (confidence, needs_clarification) in [
            ("-0.1", "false"),
            ("1.1", "false"),
            ("\"NaN\"", "false"),
            ("\"not-a-number\"", "false"),
            ("\" 0.0_5 \"", "false"),
            ("0.5", "2"),
            ("0.5", "0.5"),
            ("0.5", "\" true \""),
            ("0.5", "\"maybe\""),
        ] {
            let json = classification_with_scalars(confidence, needs_clarification);
            assert!(serde_json::from_str::<Classification>(&json).is_err());
        }
    }
}
