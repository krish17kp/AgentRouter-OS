//! JSON probe for a complete model inventory and classification.
//! Used for differential testing across routing dimensions, independent of
//! the handpicked routing-gold scenarios.
use std::io::{self, Read};

use agentrouter_core::Classification;
use agentrouter_registry::ModelEntry;
use agentrouter_routing::{route, Weights};
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    models: Vec<ModelEntry>,
    classification: Classification,
    preference: Option<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    if request
        .preference
        .as_deref()
        .is_some_and(|name| !agentrouter_policy::preference_weights().contains_key(name))
    {
        return Err("unknown routing preference".into());
    }
    let result = route(
        &request.models,
        &request.classification,
        Weights::default(),
        request.preference.as_deref(),
    );
    println!("{}", serde_json::to_string(&result)?);
    Ok(())
}
