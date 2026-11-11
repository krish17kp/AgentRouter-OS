//! Offline fixture probe for evaluation schema and normalized-hash parity.

use std::io::{self, Read};

use agentrouter_evaluation::EvaluationCase;
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    cases: Vec<EvaluationCase>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    for case in &request.cases {
        case.validate()?;
    }
    let checksums: Vec<_> = request
        .cases
        .iter()
        .map(EvaluationCase::task_hash)
        .collect();
    println!(
        "{}",
        json!({ "cases": request.cases, "task_hashes": checksums })
    );
    Ok(())
}
