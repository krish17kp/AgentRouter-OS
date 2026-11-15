//! Offline seven-dimension grading probe with an injected classifier result.

use agentrouter_core::Classification;
use agentrouter_evaluation::{
    runner::{run_all_dimensions_with, RunOptions},
    EvaluationCase,
};
use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Request {
    cases: Vec<EvaluationCase>,
    commands: Vec<String>,
    groups: Vec<String>,
    prediction: Classification,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let models =
        agentrouter_evaluation::evaluators_api::load_seed_models().map_err(io::Error::other)?;
    let report = run_all_dimensions_with(
        &request.cases,
        &models,
        &request.commands,
        &request.groups,
        RunOptions {
            profile: None,
            seed: 0,
            source: "fixture".to_owned(),
            environment: serde_json::Value::Null,
            datasets: serde_json::Value::Null,
            context_band_generalization: None,
        },
        &|_| request.prediction.clone(),
    )
    .map_err(io::Error::other)?;
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
