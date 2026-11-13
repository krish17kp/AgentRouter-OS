//! Request schemas from `agentrouter.server.schemas`.
//!
//! This crate currently ports request validation only. The Python FastAPI
//! service remains the shipping server until its lifecycle, middleware and
//! response contracts are ported as well.

use agentrouter_core::Level;
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const MAX_TASK_CHARS: usize = 100_000;
pub const MAX_NOTE_CHARS: usize = 10_000;
pub const MAX_TOOLS: usize = 100;
pub const MAX_DECISION_ID_CHARS: usize = 200;
pub const MAX_PREFER_CHARS: usize = 200;

#[derive(Debug, Clone, Copy)]
pub enum RequestKind {
    Classify,
    Route,
    Feedback,
    DryRun,
}

/// Return FastAPI/Pydantic's first public validation message for a JSON value.
///
/// The API surface intentionally reports one error at a time, matching the
/// existing Python handler. The typed deserializer still owns conversion after
/// this check; this function only keeps the observable error envelope and wording
/// compatible for the request fields we support.
pub fn first_validation_message(value: &Value, kind: RequestKind) -> Option<String> {
    if value.is_null() {
        return Some("Field required".to_string());
    }
    let Some(object) = value.as_object() else {
        return Some(
            "Input should be a valid dictionary or object to extract fields from".to_string(),
        );
    };

    match kind {
        RequestKind::Classify | RequestKind::Route => {
            if let Some(message) = required_string(object, "task", 1, Some(MAX_TASK_CHARS)) {
                return Some(message);
            }
            if let Some(value) = object
                .get("context_tokens")
                .filter(|value| !value.is_null())
            {
                if let Some(number) = pydantic_integer(value) {
                    if number <= 0 {
                        return Some(field_error(
                            "context_tokens",
                            "Input should be greater than 0",
                        ));
                    }
                } else {
                    return Some(field_error("context_tokens", integer_error(value)));
                }
            }
            if let Some(value) = object.get("risk").filter(|value| !value.is_null()) {
                if !matches!(value.as_str(), Some("low" | "medium" | "high")) {
                    return Some(field_error(
                        "risk",
                        "Input should be 'low', 'medium' or 'high'",
                    ));
                }
            }
            if let Some(value) = object.get("tools").filter(|value| !value.is_null()) {
                let Some(tools) = value.as_array() else {
                    return Some(field_error("tools", "Input should be a valid list"));
                };
                for (index, tool) in tools.iter().enumerate() {
                    if !tool.is_string() {
                        return Some(field_error(
                            &format!("tools.{index}"),
                            "Input should be a valid string",
                        ));
                    }
                }
                if tools.len() > MAX_TOOLS {
                    return Some(field_error(
                        "tools",
                        &format!(
                            "List should have at most {MAX_TOOLS} items after validation, not {}",
                            tools.len()
                        ),
                    ));
                }
            }
            if matches!(kind, RequestKind::Route) {
                if let Some(value) = object.get("prefer").filter(|value| !value.is_null()) {
                    if let Some(message) = optional_string("prefer", value, Some(MAX_PREFER_CHARS))
                    {
                        return Some(message);
                    }
                }
                if let Some(value) = object.get("no_log").filter(|value| !value.is_null()) {
                    if !pydantic_boolean(value) {
                        return Some(field_error(
                            "no_log",
                            "Input should be a valid boolean, unable to interpret input",
                        ));
                    }
                }
            }
        }
        RequestKind::Feedback => {
            if let Some(message) =
                required_string(object, "decision_id", 1, Some(MAX_DECISION_ID_CHARS))
            {
                return Some(message);
            }
            let Some(rating) = object.get("rating") else {
                return Some(field_error("rating", "Field required"));
            };
            let Some(rating) = pydantic_integer(rating) else {
                return Some(field_error("rating", integer_error(rating)));
            };
            if rating < 1 {
                return Some(field_error(
                    "rating",
                    "Input should be greater than or equal to 1",
                ));
            }
            if rating > 5 {
                return Some(field_error(
                    "rating",
                    "Input should be less than or equal to 5",
                ));
            }
            if let Some(value) = object.get("note").filter(|value| !value.is_null()) {
                if let Some(message) = optional_string("note", value, Some(MAX_NOTE_CHARS)) {
                    return Some(message);
                }
            }
        }
        RequestKind::DryRun => {
            if let Some(message) =
                required_string(object, "decision_id", 1, Some(MAX_DECISION_ID_CHARS))
            {
                return Some(message);
            }
        }
    }
    None
}

fn required_string(
    object: &serde_json::Map<String, Value>,
    field: &str,
    min_length: usize,
    max_length: Option<usize>,
) -> Option<String> {
    let Some(value) = object.get(field) else {
        return Some(field_error(field, "Field required"));
    };
    if value.is_null() || !value.is_string() {
        return Some(field_error(field, "Input should be a valid string"));
    }
    string_length_error(
        field,
        value.as_str().unwrap_or_default(),
        min_length,
        max_length,
    )
}

fn optional_string(field: &str, value: &Value, max_length: Option<usize>) -> Option<String> {
    let Some(value) = value.as_str() else {
        return Some(field_error(field, "Input should be a valid string"));
    };
    string_length_error(field, value, 0, max_length)
}

fn string_length_error(
    field: &str,
    value: &str,
    min_length: usize,
    max_length: Option<usize>,
) -> Option<String> {
    let length = value.chars().count();
    if length < min_length {
        return Some(field_error(
            field,
            "String should have at least 1 character",
        ));
    }
    if let Some(max_length) = max_length.filter(|max| length > *max) {
        return Some(field_error(
            field,
            &format!("String should have at most {max_length} characters"),
        ));
    }
    None
}

fn field_error(field: &str, message: &str) -> String {
    format!("{field}: {message}")
}

fn integer_error(value: &Value) -> &'static str {
    match value {
        Value::Number(number) if number.as_f64().is_some_and(|value| value.fract() != 0.0) => {
            "Input should be a valid integer, got a number with a fractional part"
        }
        Value::String(_) => "Input should be a valid integer, unable to parse string as an integer",
        _ => "Input should be a valid integer",
    }
}

fn pydantic_integer(value: &Value) -> Option<i64> {
    match value {
        Value::Bool(value) => Some(i64::from(*value)),
        Value::Number(number) => number
            .as_i64()
            .or_else(|| number.as_u64().and_then(|value| i64::try_from(value).ok()))
            .or_else(|| {
                number.as_f64().and_then(|value| {
                    (value.is_finite()
                        && value.fract() == 0.0
                        && value >= i64::MIN as f64
                        && value < -(i64::MIN as f64))
                        .then_some(value as i64)
                })
            }),
        Value::String(value) => crate::pydantic::parse_integer(value).ok(),
        _ => None,
    }
}

fn pydantic_boolean(value: &Value) -> bool {
    match value {
        Value::Bool(_) => true,
        Value::Number(number) => {
            number.as_i64().is_some_and(|value| matches!(value, 0 | 1))
                || number.as_u64().is_some_and(|value| value <= 1)
                || number
                    .as_f64()
                    .is_some_and(|value| matches!(value, 0.0 | 1.0))
        }
        Value::String(value) => matches!(
            value.trim().to_ascii_lowercase().as_str(),
            "0" | "off" | "false" | "no" | "n" | "f" | "1" | "on" | "true" | "yes" | "y" | "t"
        ),
        _ => false,
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClassifyRequest {
    pub task: String,
    #[serde(default, deserialize_with = "crate::pydantic::optional_i64")]
    pub context_tokens: Option<i64>,
    #[serde(default)]
    pub risk: Option<Level>,
    #[serde(default)]
    pub tools: Option<Vec<String>>,
}

impl ClassifyRequest {
    pub fn validate(&self) -> Result<(), ValidationError> {
        if self.task.is_empty() {
            return Err(ValidationError::new("task", "must not be empty"));
        }
        if self.task.chars().count() > MAX_TASK_CHARS {
            return Err(ValidationError::new(
                "task",
                "is longer than 100000 characters",
            ));
        }
        if self.context_tokens.is_some_and(|value| value <= 0) {
            return Err(ValidationError::new(
                "context_tokens",
                "must be greater than 0",
            ));
        }
        if self
            .tools
            .as_ref()
            .is_some_and(|tools| tools.len() > MAX_TOOLS)
        {
            return Err(ValidationError::new(
                "tools",
                "must contain at most 100 items",
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RouteRequest {
    #[serde(flatten)]
    pub classify: ClassifyRequest,
    #[serde(default)]
    pub prefer: Option<String>,
    #[serde(default)]
    #[serde(deserialize_with = "crate::pydantic::boolean")]
    pub no_log: bool,
}

impl RouteRequest {
    pub fn validate(&self) -> Result<(), ValidationError> {
        self.classify.validate()?;
        if self
            .prefer
            .as_ref()
            .is_some_and(|prefer| prefer.chars().count() > MAX_PREFER_CHARS)
        {
            return Err(ValidationError::new(
                "prefer",
                "is longer than 200 characters",
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeedbackRequest {
    pub decision_id: String,
    #[serde(deserialize_with = "crate::pydantic::i64")]
    pub rating: i64,
    #[serde(default)]
    pub note: Option<String>,
}

impl FeedbackRequest {
    pub fn validate(&self) -> Result<(), ValidationError> {
        validate_decision_id(&self.decision_id)?;
        if !(1..=5).contains(&self.rating) {
            return Err(ValidationError::new("rating", "must be between 1 and 5"));
        }
        if self
            .note
            .as_ref()
            .is_some_and(|note| note.chars().count() > MAX_NOTE_CHARS)
        {
            return Err(ValidationError::new(
                "note",
                "is longer than 10000 characters",
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DryRunRequest {
    pub decision_id: String,
}

impl DryRunRequest {
    pub fn validate(&self) -> Result<(), ValidationError> {
        validate_decision_id(&self.decision_id)
    }
}

fn validate_decision_id(value: &str) -> Result<(), ValidationError> {
    let length = value.chars().count();
    if length == 0 {
        return Err(ValidationError::new("decision_id", "must not be empty"));
    }
    if length > MAX_DECISION_ID_CHARS {
        return Err(ValidationError::new(
            "decision_id",
            "is longer than 200 characters",
        ));
    }
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationError {
    pub field: &'static str,
    pub reason: &'static str,
}

impl ValidationError {
    fn new(field: &'static str, reason: &'static str) -> Self {
        Self { field, reason }
    }
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{} {}", self.field, self.reason)
    }
}

impl std::error::Error for ValidationError {}

#[cfg(test)]
mod tests {
    use super::*;

    fn classify(task: &str) -> ClassifyRequest {
        ClassifyRequest {
            task: task.to_owned(),
            context_tokens: None,
            risk: None,
            tools: None,
        }
    }

    #[test]
    fn classification_request_enforces_python_bounds() {
        assert!(classify("task").validate().is_ok());
        assert!(classify("")
            .validate()
            .unwrap_err()
            .to_string()
            .contains("task"));
        assert!(classify(&"x".repeat(MAX_TASK_CHARS + 1))
            .validate()
            .unwrap_err()
            .to_string()
            .contains("100000"));
        let mut request = classify("task");
        request.context_tokens = Some(0);
        assert!(request
            .validate()
            .unwrap_err()
            .to_string()
            .contains("context_tokens"));
        let mut request = classify("task");
        request.tools = Some(vec!["tool".into(); MAX_TOOLS + 1]);
        assert!(request
            .validate()
            .unwrap_err()
            .to_string()
            .contains("tools"));
    }

    #[test]
    fn route_request_validates_inherited_and_route_fields() {
        let mut request = RouteRequest {
            classify: classify("task"),
            prefer: None,
            no_log: false,
        };
        assert!(request.validate().is_ok());
        request.prefer = Some("p".repeat(MAX_PREFER_CHARS + 1));
        assert!(request
            .validate()
            .unwrap_err()
            .to_string()
            .contains("prefer"));
    }

    #[test]
    fn feedback_and_dry_run_enforce_id_rating_and_note_bounds() {
        let feedback = FeedbackRequest {
            decision_id: "d_1".into(),
            rating: 5,
            note: None,
        };
        assert!(feedback.validate().is_ok());
        let mut feedback = feedback;
        feedback.rating = 0;
        assert!(feedback
            .validate()
            .unwrap_err()
            .to_string()
            .contains("rating"));
        feedback.rating = 3;
        feedback.note = Some("x".repeat(MAX_NOTE_CHARS + 1));
        assert!(feedback
            .validate()
            .unwrap_err()
            .to_string()
            .contains("note"));
        assert!(DryRunRequest {
            decision_id: "".into()
        }
        .validate()
        .is_err());
        assert!(DryRunRequest {
            decision_id: "d".repeat(MAX_DECISION_ID_CHARS + 1)
        }
        .validate()
        .is_err());
    }
}
