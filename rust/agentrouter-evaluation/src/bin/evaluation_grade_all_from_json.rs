//! Offline end-to-end seven-dimension evaluation scorecard probe.

use agentrouter_evaluation::{
    context_bands::evaluate_generalization,
    runner::{run_all_dimensions, RunOptions},
    EvaluationCase,
};
use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Request {
    cases: Vec<EvaluationCase>,
    commands: Vec<String>,
    groups: Vec<String>,
    #[serde(default)]
    profile: Option<String>,
    #[serde(default)]
    seed: i64,
    #[serde(default = "default_source")]
    source: String,
    #[serde(default)]
    environment: serde_json::Value,
    #[serde(default)]
    datasets: serde_json::Value,
    #[serde(default)]
    measure_context_band: bool,
}

fn default_source() -> String {
    "fixture".to_owned()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let models =
        agentrouter_evaluation::evaluators_api::load_seed_models().map_err(io::Error::other)?;
    let generalization = if request.measure_context_band {
        Some(evaluate_generalization().map_err(io::Error::other)?)
    } else {
        None
    };
    let report = run_all_dimensions(
        &request.cases,
        &models,
        &request.commands,
        &request.groups,
        RunOptions {
            profile: request.profile,
            seed: request.seed,
            source: request.source,
            environment: request.environment,
            datasets: request.datasets,
            context_band_generalization: generalization,
        },
    )
    .map_err(io::Error::other)?;
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
