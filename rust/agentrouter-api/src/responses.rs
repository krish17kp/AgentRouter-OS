//! Response models mirrored from `agentrouter.server.schemas`.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ErrorBody {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ErrorResponse {
    pub error: ErrorBody,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ModelSummary {
    pub vendor: Option<String>,
    pub model_id: String,
    pub key: String,
    pub release_channel: String,
    #[serde(deserialize_with = "crate::pydantic::i64")]
    pub context_window: i64,
    pub host_availability: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HostStatusResponse {
    pub host: String,
    pub availability: String,
    pub reason: String,
    #[serde(default = "unknown_state")]
    pub state: String,
    #[serde(default)]
    pub remedy: Option<String>,
}

fn unknown_state() -> String {
    "unknown".to_owned()
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeedbackResponse {
    pub decision_id: String,
    #[serde(deserialize_with = "crate::pydantic::boolean")]
    pub recorded: bool,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct ClassifyResponse {
    pub task_type: Value,
    pub complexity: Value,
    pub risk: Value,
    pub context_band: Value,
    pub context_tokens: Value,
    pub output_type: Value,
    pub tool_needs: Value,
    pub approval_level: Value,
    pub confidence: Value,
    pub needs_clarification: Value,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct RouteResponse {
    pub task: Value,
    pub decision_id: Value,
    pub classification: Value,
    pub recommendation: Value,
    pub fallback: Value,
    pub execution_route: Value,
    pub fallback_execution_route: Value,
    pub scores: Value,
    pub excluded: Value,
    pub gates: Value,
    pub prompt: Value,
    pub weights: Value,
    pub weight_shifts: Value,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct DecisionResponse {
    pub task: Value,
    pub decision_id: Value,
    pub classification: Value,
    pub recommendation: Value,
    pub fallback: Value,
    pub execution_route: Value,
    pub fallback_execution_route: Value,
    pub scores: Value,
    pub excluded: Value,
    pub gates: Value,
    pub prompt: Value,
    pub weights: Value,
    pub weight_shifts: Value,
    pub created_at: Value,
    pub user: Value,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct DryRunResponse {
    pub decision_id: Value,
    pub recommendation: Value,
    pub execution_route: Value,
    pub argv: Value,
    pub would_execute: Value,
    pub auto_execute_allowed: Value,
    pub note: Value,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}
