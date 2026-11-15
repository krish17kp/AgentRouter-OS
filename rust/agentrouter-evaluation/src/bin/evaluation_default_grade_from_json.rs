//! Public default grading probe with no caller-provided runtime manifests.

use agentrouter_evaluation::EvaluationCase;
use serde::Deserialize;
use serde_json::Value;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    cases: Vec<EvaluationCase>,
    #[serde(default)]
    measure_all: bool,
    #[serde(default)]
    context_band_generalization: Option<Value>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let report = agentrouter_evaluation::runner::run_default_grade(
        &request.cases,
        request.measure_all,
        request.context_band_generalization.as_ref(),
    )
    .map_err(io::Error::other)?;
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
