//! Offline probe for Python/Rust registry differential tests.
use agentrouter_registry::{load_models, load_providers};
use serde::{Deserialize, Serialize};
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    providers_yaml: String,
    models_yaml: String,
}

#[derive(Serialize)]
struct Response {
    keys: Vec<String>,
    vendors: Vec<String>,
    warnings: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let providers = load_providers(&request.providers_yaml)?;
    let (models, warnings) = load_models(&request.models_yaml, &providers)?;
    let response = Response {
        keys: models.iter().map(|model| model.key()).collect(),
        vendors: models
            .iter()
            .map(|model| model.vendor().to_owned())
            .collect(),
        warnings,
    };
    println!("{}", serde_json::to_string(&response)?);
    Ok(())
}
