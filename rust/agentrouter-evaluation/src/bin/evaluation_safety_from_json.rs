//! Offline fixture probe for Python/Rust evaluation safety parity.

use std::io::{self, Read};

use serde::Deserialize;

#[derive(Deserialize)]
struct WithClassifier {
    cases: Vec<agentrouter_evaluation::EvaluationCase>,
    #[serde(default)]
    classifier_by_task: std::collections::HashMap<String, agentrouter_core::Classification>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let value: serde_json::Value = serde_json::from_str(&input)?;
    let report = if value.is_array() {
        let cases: Vec<agentrouter_evaluation::EvaluationCase> = serde_json::from_value(value)?;
        agentrouter_evaluation::evaluate_safety(&cases)
    } else {
        let input: WithClassifier = serde_json::from_value(value)?;
        agentrouter_evaluation::evaluate_safety_with(&input.cases, |task| {
            input
                .classifier_by_task
                .get(task)
                .cloned()
                .unwrap_or_else(|| {
                    agentrouter_classifier::classify(
                        task,
                        &agentrouter_classifier::ClassifyOptions::default(),
                    )
                })
        })
    };
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
