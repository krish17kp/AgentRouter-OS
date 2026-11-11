//! Measure classification and routing latency for supplied offline fixtures.

use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Input {
    models: Vec<agentrouter_registry::ModelEntry>,
    tasks: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    println!(
        "{}",
        serde_json::to_string(&agentrouter_evaluation::evaluate_performance(
            &input.models,
            &input.tasks
        ))?
    );
    Ok(())
}
