use std::io::{self, Read};

use agentrouter_evaluation::{
    context_bands::evaluate_generalization, runner::run_classification, EvaluationCase,
};
use serde::Deserialize;

#[derive(Deserialize)]
struct Request {
    cases: Vec<EvaluationCase>,
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
    let generalization = if request.measure_context_band {
        Some(evaluate_generalization().map_err(io::Error::other)?)
    } else {
        None
    };
    let report = run_classification(
        &request.cases,
        request.profile.as_deref(),
        request.seed,
        &request.source,
        request.environment,
        request.datasets,
        generalization.as_ref(),
    );
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
