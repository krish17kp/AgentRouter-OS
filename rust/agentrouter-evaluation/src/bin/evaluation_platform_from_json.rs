//! Offline fixture probe for Python/Rust CLI platform evaluator parity.

use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Input {
    commands: Vec<String>,
    groups: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    println!(
        "{}",
        serde_json::to_string(&agentrouter_evaluation::evaluate_platform(
            &input.commands,
            &input.groups
        ))?
    );
    Ok(())
}
