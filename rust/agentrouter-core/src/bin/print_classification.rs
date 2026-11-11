//! Prints a fixed `Classification` as JSON so the Python/Rust compatibility
//! test (`tests/test_rust_compat.py`) can diff it against the Python schema's
//! serialization of the same values, without either side depending on the
//! other at compile time.

use agentrouter_core::{ApprovalLevel, Classification, ContextBand, Level, OutputType, TaskType};

fn main() {
    let c = Classification {
        task_type: TaskType::Coding,
        complexity: Level::Medium,
        risk: Level::Low,
        context_tokens: 1200,
        context_band: ContextBand::Small,
        output_type: OutputType::CodeTests,
        tool_needs: vec!["filesystem".to_string()],
        approval_level: ApprovalLevel::HumanApprovalRequired,
        confidence: 1.0,
        needs_clarification: false,
        alternative_task_type: None,
        ambiguity_reason: None,
    };
    println!("{}", serde_json::to_string(&c).unwrap());
}
