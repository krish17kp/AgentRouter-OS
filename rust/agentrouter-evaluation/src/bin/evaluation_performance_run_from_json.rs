//! Measure classification and routing latency for supplied offline fixtures.

use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Input {
    models: Option<Vec<agentrouter_registry::ModelEntry>>,
    tasks: Option<Vec<String>>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let report = match (input.models, input.tasks) {
        (None, None) => agentrouter_evaluation::evaluate_default_performance()?,
        (models, tasks) => {
            let models = match models {
                Some(models) => models,
                None => agentrouter_evaluation::evaluators_api::load_seed_models()?,
            };
            let tasks = tasks.unwrap_or_else(|| {
                agentrouter_evaluation::PERFORMANCE_SAMPLE_TASKS
                    .iter()
                    .map(|task| (*task).to_owned())
                    .collect()
            });
            agentrouter_evaluation::evaluate_performance(&models, &tasks)
        }
    };
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
