//! Static safety gate parity with `agentrouter.safety.gates_for`.
use agentrouter_core::{ApprovalLevel, Classification, Level};
use serde::Serialize;

#[derive(Debug, PartialEq, Serialize)]
pub struct SafetyGates {
    pub checklist: Vec<&'static str>,
    pub auto_execute_allowed: bool,
    pub approval_level: &'static str,
}

pub fn gates_for(classification: &Classification) -> SafetyGates {
    let checklist = match classification.risk {
        Level::Low => vec!["Sanity-check the output before using it"],
        Level::Medium => vec![
            "Review the output before acting on it",
            "Run relevant tests / verify behavior",
            "Confirm the change stays within intended scope",
        ],
        Level::High => vec![
            "Review full diff before applying",
            "Run the test suite",
            "Secret scan changed files",
            "Confirm rollback path",
            "Human sign-off (no auto-execute)",
        ],
    };
    let approval_level = match classification.approval_level {
        ApprovalLevel::Auto => "auto",
        ApprovalLevel::Notify => "notify",
        ApprovalLevel::HumanApprovalRequired => "human-approval-required",
    };
    SafetyGates {
        checklist,
        auto_execute_allowed: classification.risk != Level::High
            && classification.approval_level == ApprovalLevel::Auto,
        approval_level,
    }
}
