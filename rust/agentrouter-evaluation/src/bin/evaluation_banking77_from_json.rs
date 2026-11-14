//! Offline differential probe for Banking77 raw-row normalization.

use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    label_names: Vec<String>,
    rows: Vec<agentrouter_evaluation::Banking77RawRow>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    match agentrouter_evaluation::normalize_banking77_rows(&input.label_names, &input.rows) {
        Ok(cases) => println!("{}", serde_json::to_string(&cases)?),
        Err(error) => println!("{}", serde_json::json!({"error": error})),
    }
    Ok(())
}
