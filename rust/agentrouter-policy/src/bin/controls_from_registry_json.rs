//! Offline route-control parity probe. Host availability is supplied as
//! explicit evidence; missing entries are unavailable.
use agentrouter_policy::controls::{apply_controls, RouteControls};
use agentrouter_registry::{load_models, load_providers};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    providers_yaml: String,
    models_yaml: String,
    controls: RouteControls,
    #[serde(default)]
    available: HashMap<String, bool>,
}

#[derive(Serialize)]
struct Response {
    kept: Vec<String>,
    dropped: Vec<agentrouter_policy::controls::Exclusion>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let providers = load_providers(&request.providers_yaml)?;
    let (models, _) = load_models(&request.models_yaml, &providers)?;
    let (kept, dropped) = apply_controls(&models, &request.controls, &request.available);
    println!(
        "{}",
        serde_json::to_string(&Response {
            kept: kept.iter().map(|model| model.key()).collect(),
            dropped,
        })?
    );
    Ok(())
}
