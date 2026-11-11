//! Offline probe for AgentRouter gold dataset loading parity.

use serde::Deserialize;
use serde_json::json;
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    path: PathBuf,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let cases = match agentrouter_evaluation::load_agentrouter_gold(&input.path) {
        Ok(cases) => cases,
        Err(error) => {
            println!(
                "{}",
                serde_json::to_string(&json!({
                    "error": error,
                    "availability": agentrouter_evaluation::agentrouter_gold_availability(&input.path),
                }))?
            );
            return Ok(());
        }
    };
    let sample = agentrouter_evaluation::agentrouter_gold_sample(&input.path, Some(20), 5)?;
    let all_sample = agentrouter_evaluation::agentrouter_gold_sample(&input.path, None, 5)?;
    let empty_sample = agentrouter_evaluation::agentrouter_gold_sample(&input.path, Some(0), 5)?;
    println!(
        "{}",
        serde_json::to_string(&json!({
            "cases": cases,
            "metadata": agentrouter_evaluation::agentrouter_gold_metadata(),
            "availability": agentrouter_evaluation::agentrouter_gold_availability(&input.path),
            "describe": agentrouter_evaluation::agentrouter_gold_describe(&input.path),
            "checksum": agentrouter_evaluation::agentrouter_gold_checksum(&input.path)?,
            "sample": sample,
            "all_sample": all_sample,
            "empty_sample": empty_sample,
        }))?
    );
    Ok(())
}
