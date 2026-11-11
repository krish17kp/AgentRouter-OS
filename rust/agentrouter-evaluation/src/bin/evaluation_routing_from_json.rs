//! Offline fixture probe for Python/Rust evaluation routing parity.

use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Input {
    cases: Vec<agentrouter_evaluation::EvaluationCase>,
    models: Vec<agentrouter_registry::ModelEntry>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    println!(
        "{}",
        serde_json::to_string(&agentrouter_evaluation::evaluate_routing(
            &input.cases,
            &input.models
        ))?
    );
    Ok(())
}
