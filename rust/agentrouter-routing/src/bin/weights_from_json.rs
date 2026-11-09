//! Small JSON probe for Python/Rust differential testing. No service is started.
use agentrouter_core::Classification;
use agentrouter_routing::{weights_for, Preference, Weights};
use serde::{Deserialize, Serialize};
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    classification: Classification,
    #[serde(default)]
    base: Option<Weights>,
    #[serde(default)]
    preference: Option<Preference>,
}

#[derive(Serialize)]
struct Response {
    weights: Weights,
    shifts: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let (weights, shifts) = weights_for(&request.classification, request.base, request.preference);
    println!("{}", serde_json::to_string(&Response { weights, shifts })?);
    Ok(())
}
