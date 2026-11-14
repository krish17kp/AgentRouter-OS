//! Offline fixture probe for Python/Rust evaluation routing parity.

use serde::Deserialize;
use std::collections::HashMap;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Input {
    cases: Vec<agentrouter_evaluation::EvaluationCase>,
    models: Vec<agentrouter_registry::ModelEntry>,
    #[serde(default)]
    classifier_by_task: HashMap<String, agentrouter_core::Classification>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let report =
        agentrouter_evaluation::evaluate_routing_with(&input.cases, &input.models, |task| {
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
        });
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
