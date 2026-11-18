//! Offline fixture probe for evaluation registry/profile parity.

use std::collections::BTreeMap;
use std::io::{self, Read};

use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    profiles: Vec<String>,
    names: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let profiles = request
        .profiles
        .iter()
        .map(|name| {
            agentrouter_evaluation::profile_datasets(name).map(|datasets| (name.clone(), datasets))
        })
        .collect::<Result<BTreeMap<_, _>, _>>()?;
    let adapters = request
        .names
        .iter()
        .map(|name| agentrouter_evaluation::adapter_descriptor(name))
        .collect::<Result<Vec<_>, _>>()?;
    println!(
        "{}",
        json!({
            "dataset_names": agentrouter_evaluation::DATASET_NAMES,
            "profiles": profiles,
            "adapters": adapters,
        })
    );
    Ok(())
}
