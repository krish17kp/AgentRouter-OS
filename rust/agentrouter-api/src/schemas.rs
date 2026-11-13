//! Request schemas from `agentrouter.server.schemas`.
//!
//! This crate currently ports request validation only. The Python FastAPI
//! service remains the shipping server until its lifecycle, middleware and
//! response contracts are ported as well.

use agentrouter_core::Level;
use serde::{Deserialize, Serialize};

pub const MAX_TASK_CHARS: usize = 100_000;
pub const MAX_NOTE_CHARS: usize = 10_000;
pub const MAX_TOOLS: usize = 100;
pub const MAX_DECISION_ID_CHARS: usize = 200;
pub const MAX_PREFER_CHARS: usize = 200;

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
