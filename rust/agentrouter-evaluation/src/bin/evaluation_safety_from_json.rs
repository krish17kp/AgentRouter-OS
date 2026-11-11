//! Offline fixture probe for Python/Rust evaluation safety parity.

use std::io::{self, Read};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let cases: Vec<agentrouter_evaluation::EvaluationCase> = serde_json::from_str(&input)?;
    println!(
        "{}",
        serde_json::to_string(&agentrouter_evaluation::evaluate_safety(&cases))?
    );
    Ok(())
}
