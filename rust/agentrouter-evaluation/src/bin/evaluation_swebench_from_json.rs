//! Offline differential probe for SWE-bench Lite row preparation.

use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    rows: Vec<agentrouter_evaluation::SWEBenchRawRow>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let cases = agentrouter_evaluation::normalize_swebench_rows(&input.rows);
    println!("{}", serde_json::to_string(&cases)?);
    Ok(())
}
