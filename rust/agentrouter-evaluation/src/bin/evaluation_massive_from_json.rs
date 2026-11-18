//! Offline differential probe for MASSIVE locale row normalization.

use serde::Deserialize;
use std::collections::BTreeMap;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    #[serde(default)]
    languages: Option<Vec<String>>,
    datasets: BTreeMap<String, Vec<agentrouter_evaluation::MassiveRawRow>>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    match agentrouter_evaluation::normalize_massive_rows(
        input.languages.as_deref(),
        &input.datasets,
    ) {
        Ok(cases) => println!("{}", serde_json::to_string(&cases)?),
        Err(error) => println!("{}", serde_json::json!({"error": error})),
    }
    Ok(())
}
