//! Fail-closed execution planning.
//!
//! This crate deliberately does not start a process, call a provider, read a
//! credential, or expose an execution adapter. It turns a routed model and
//! classification into an auditable plan and blocks anything that is not
//! explicitly safe and locally available. Actual adapters remain a separate,
//! owner-authorized milestone.

use agentrouter_core::{ApprovalLevel, Classification, Level};
use agentrouter_hosts::{resolve_execution_route, AVAILABLE};
use agentrouter_registry::{ExecutionMode, ModelEntry};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionStatus {
    Planned,
    Blocked,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionPolicy {
    pub remote_enabled: bool,
    pub approval_granted: bool,
    pub include_unavailable: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutionPlan {
    pub status: ExecutionStatus,
    pub execution_enabled: bool,
    pub model: String,
    pub host: Option<String>,
    pub mode: Option<ExecutionMode>,
    pub command_preview: Option<String>,
    pub reason: String,
    pub requires_approval: bool,
}

#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum PlanError {
    #[error("execution planning requires a routed recommendation")]
    NoRecommendation,
    #[error("high-risk work requires explicit human approval")]
    ApprovalRequired,
    #[error("execution host is unavailable: {0}")]
    HostUnavailable(String),
    #[error("no execution target is registered for model '{0}'")]
    NoTarget(String),
    #[error("remote/API execution is disabled by policy")]
    RemoteDisabled,
    #[error("no execution adapter is registered for host '{0}'")]
    AdapterUnavailable(String),
}

/// Build a safe execution plan. This function never executes the returned
/// plan; `execution_enabled` remains false until a separately authorized
/// adapter milestone changes that contract.
pub fn plan(
    model: &ModelEntry,
    classification: &Classification,
    policy: ExecutionPolicy,
) -> Result<ExecutionPlan, PlanError> {
    let route = resolve_execution_route(model, policy.include_unavailable);
    let target = route
        .target
        .ok_or_else(|| PlanError::NoTarget(model.key()))?;
    let status = route
        .status
        .as_ref()
        .ok_or_else(|| PlanError::NoTarget(model.key()))?;
    let requires_approval = classification.risk == Level::High
        || classification.approval_level == ApprovalLevel::HumanApprovalRequired;
    if requires_approval && !policy.approval_granted {
        return Err(PlanError::ApprovalRequired);
    }
    if status.availability != AVAILABLE && !policy.include_unavailable {
        return Err(PlanError::HostUnavailable(status.reason.clone()));
    }
    if target.execution_mode == ExecutionMode::Api {
        if !policy.remote_enabled {
            return Err(PlanError::RemoteDisabled);
        }
        return Err(PlanError::AdapterUnavailable(target.host.clone()));
    }
    if target.execution_mode == ExecutionMode::Manual {
        return Ok(ExecutionPlan {
            status: ExecutionStatus::Blocked,
            execution_enabled: false,
            model: model.key(),
            host: Some(target.host.clone()),
            mode: Some(target.execution_mode),
            command_preview: Some(agentrouter_hosts::command_preview(target, true)),
            reason: "manual execution requires an explicit operator handoff".to_string(),
            requires_approval,
        });
    }
    if !target.supports_noninteractive {
        return Err(PlanError::AdapterUnavailable(target.host.clone()));
    }
    Ok(ExecutionPlan {
        status: ExecutionStatus::Planned,
        execution_enabled: false,
        model: model.key(),
        host: Some(target.host.clone()),
        mode: Some(target.execution_mode),
        command_preview: Some(agentrouter_hosts::command_preview(target, true)),
        reason: "plan created; no execution adapter is enabled".to_string(),
        requires_approval,
    })
}

#[cfg(test)]
mod tests {
    use super::{plan, ExecutionPolicy, ExecutionStatus, PlanError};
    use agentrouter_core::{
        ApprovalLevel, Classification, ContextBand, Level, OutputType, TaskType,
    };
    use agentrouter_registry::ModelEntry;

    fn classification(risk: Level, approval_level: ApprovalLevel) -> Classification {
        Classification {
            task_type: TaskType::General,
            complexity: Level::Low,
            risk,
            context_tokens: 1.into(),
            context_band: ContextBand::Small,
            output_type: OutputType::Text,
            tool_needs: Vec::new(),
            approval_level,
            confidence: 1.0,
            needs_clarification: false,
            alternative_task_type: None,
            ambiguity_reason: None,
        }
    }

    fn model(mode: &str) -> ModelEntry {
        let yaml = format!(
            "provider: p\nmodel_id: m\ncontext_window: 1000\nmax_output_tokens: 100\npricing_tier: low\nlatency_tier: fast\nability: {{coding: 5, reasoning: 5, writing: 5}}\ntool_support: []\nvision_support: false\ndeprecation_status: active\nexecution_targets:\n  - host: openai-api\n    host_model_id: m\n    execution_mode: {mode}\n"
        );
        serde_yaml::from_str(&yaml).expect("valid model fixture")
    }

    #[test]
    fn default_policy_disables_remote_execution_and_approval() {
        let policy = ExecutionPolicy::default();
        assert!(!policy.remote_enabled);
        assert!(!policy.approval_granted);
        assert!(!policy.include_unavailable);
    }

    #[test]
    fn blocks_high_risk_without_approval() {
        let error = plan(
            &model("api"),
            &classification(Level::High, ApprovalLevel::Auto),
            ExecutionPolicy {
                include_unavailable: true,
                ..ExecutionPolicy::default()
            },
        )
        .expect_err("approval is mandatory");
        assert_eq!(error, PlanError::ApprovalRequired);
    }

    #[test]
    fn keeps_api_execution_disabled_even_when_host_is_included() {
        let error = plan(
            &model("api"),
            &classification(Level::Low, ApprovalLevel::Auto),
            ExecutionPolicy {
                include_unavailable: true,
                ..ExecutionPolicy::default()
            },
        )
        .expect_err("remote execution is disabled by default");
        assert_eq!(error, PlanError::RemoteDisabled);
    }

    #[test]
    fn manual_route_is_an_explicit_operator_handoff() {
        let planned = plan(
            &model("manual"),
            &classification(Level::Low, ApprovalLevel::Auto),
            ExecutionPolicy {
                include_unavailable: true,
                ..ExecutionPolicy::default()
            },
        )
        .expect("manual planning should be representable");
        assert_eq!(planned.status, ExecutionStatus::Blocked);
        assert!(!planned.execution_enabled);
        assert!(planned.reason.contains("operator handoff"));
    }
}
