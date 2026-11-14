//! Offline fixture probe for Python/Rust provider metadata evaluator parity.

use std::io::{self, Read};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: serde_json::Value = serde_json::from_str(&input)?;
    let models = if input.is_array() {
        Some(serde_json::from_value::<
            Vec<agentrouter_registry::ModelEntry>,
        >(input)?)
    } else {
        input
            .get("models")
            .filter(|value| !value.is_null())
            .cloned()
            .map(serde_json::from_value::<Vec<agentrouter_registry::ModelEntry>>)
            .transpose()?
    };
    let report = match models {
        Some(models) => agentrouter_evaluation::evaluate_provider(&models),
        None => agentrouter_evaluation::evaluate_provider_default()?,
    };
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
