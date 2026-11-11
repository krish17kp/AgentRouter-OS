//! Offline fixture probe for classification-only evaluation grading parity.

use std::io::{self, Read};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: serde_json::Value = serde_json::from_str(&input)?;
    let n_cases = input["n_cases"].as_u64().unwrap_or(0) as usize;
    let generalization = input.get("context_band_generalization");
    let result = agentrouter_evaluation::grade_classification(
        &input["classification"],
        n_cases,
        generalization,
    );
    println!("{}", serde_json::to_string(&result)?);
    Ok(())
}
