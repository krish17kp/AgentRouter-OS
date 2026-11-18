//! Offline fixture probe for Python/Rust classification metric parity.

use std::io::{self, Read};

use agentrouter_evaluation::MetricCase;
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    cases: Vec<MetricCase>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    println!(
        "{}",
        agentrouter_evaluation::classification_metrics(&request.cases)
    );
    Ok(())
}
