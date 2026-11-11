//! Offline fixture probe for Python/Rust dataset-quality report parity.

use std::io::{self, Read};

use agentrouter_evaluation::QualityCase;
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    cases: Vec<QualityCase>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    println!(
        "{}",
        agentrouter_evaluation::dataset_quality(&request.cases)
    );
    Ok(())
}
