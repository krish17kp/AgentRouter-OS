//! End-to-end offline evaluation runner using the Rust dataset registry.

use agentrouter_evaluation::runner::{run_registered, RegisteredRunOptions};
use serde::Deserialize;
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    project_root: PathBuf,
    #[serde(default)]
    dataset: Option<String>,
    #[serde(default)]
    profile: Option<String>,
    #[serde(default)]
    limit: Option<i64>,
    #[serde(default)]
    seed: i64,
    #[serde(default = "default_source")]
    source: String,
    #[serde(default)]
    languages: Option<Vec<String>>,
    #[serde(default)]
    measure_all: bool,
    #[serde(default)]
    commands: Vec<String>,
    #[serde(default)]
    groups: Vec<String>,
    #[serde(default)]
    environment: serde_json::Value,
}

fn default_source() -> String {
    "fixture".to_owned()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let report = run_registered(RegisteredRunOptions {
        project_root: request.project_root,
        dataset: request.dataset,
        profile: request.profile,
        limit: request.limit,
        seed: request.seed,
        source: request.source,
        languages: request.languages,
        measure_all: request.measure_all,
        commands: request.commands,
        groups: request.groups,
        environment: request.environment,
    })
    .map_err(io::Error::other)?;
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
