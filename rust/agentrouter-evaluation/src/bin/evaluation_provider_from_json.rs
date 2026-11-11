//! Offline fixture probe for Python/Rust provider metadata evaluator parity.

use std::io::{self, Read};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let models: Vec<agentrouter_registry::ModelEntry> = serde_json::from_str(&input)?;
    println!(
        "{}",
        serde_json::to_string(&agentrouter_evaluation::evaluate_provider(&models))?
    );
    Ok(())
}
