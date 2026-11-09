//! JSON probe for differential tests; it never executes a model or accesses hosts.
use agentrouter_core::Classification;
use agentrouter_routing::decision::{route, RouteModel};
use agentrouter_routing::{Preference, Weights};
use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    models: Vec<RouteModel>,
    classification: Classification,
    #[serde(default)]
    base: Option<Weights>,
    #[serde(default)]
    preference: Option<Preference>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let decision = route(
        &request.models,
        &request.classification,
        request.base,
        request.preference,
    );
    println!("{}", serde_json::to_string(&decision)?);
    Ok(())
}
