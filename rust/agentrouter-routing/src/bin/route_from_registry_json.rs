//! End-to-end offline YAML registry to static decision probe.
use agentrouter_core::Classification;
use agentrouter_policy::controls::{apply_controls, RouteControls};
use agentrouter_registry::{load_models, load_providers};
use agentrouter_routing::decision::{route, Exclusion, RouteModel};
use agentrouter_routing::{Preference, Weights};
use serde::Deserialize;
use std::collections::HashMap;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    providers_yaml: String,
    models_yaml: String,
    classification: Classification,
    #[serde(default)]
    base: Option<Weights>,
    #[serde(default)]
    preference: Option<Preference>,
    #[serde(default)]
    controls: RouteControls,
    #[serde(default)]
    available: HashMap<String, bool>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let providers = load_providers(&request.providers_yaml)?;
    let (models, _) = load_models(&request.models_yaml, &providers)?;
    let (kept, dropped) = apply_controls(&models, &request.controls, &request.available);
    let candidates: Vec<RouteModel> = kept.into_iter().map(RouteModel::from).collect();
    let mut decision = route(
        &candidates,
        &request.classification,
        request.base,
        request.preference,
    );
    let mut exclusions: Vec<Exclusion> = dropped
        .into_iter()
        .map(|row| Exclusion {
            model: row.model,
            reason: row.reason,
        })
        .collect();
    exclusions.append(&mut decision.excluded);
    decision.excluded = exclusions;
    println!("{}", serde_json::to_string(&decision)?);
    Ok(())
}
