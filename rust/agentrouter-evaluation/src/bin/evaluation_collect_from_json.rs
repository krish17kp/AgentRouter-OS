//! Registered fixture collection and sampling probe for evaluation profiles.

use agentrouter_evaluation::registry_api::collect;
use serde::Deserialize;
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    project_root: PathBuf,
    names: Vec<String>,
    #[serde(default)]
    limit: Option<i64>,
    #[serde(default)]
    seed: i64,
    #[serde(default = "default_source")]
    source: String,
    #[serde(default)]
    massive_languages: Option<Vec<String>>,
}

fn default_source() -> String {
    "fixture".to_owned()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let names = request.names.iter().map(String::as_str).collect::<Vec<_>>();
    let collection = collect(
        &names,
        &request.project_root,
        request.limit,
        request.seed,
        &request.source,
        request.massive_languages.as_deref(),
    )
    .map_err(io::Error::other)?;
    println!(
        "{}",
        serde_json::to_string(&serde_json::json!({
            "cases": collection.cases,
            "datasets": collection.datasets,
        }))?
    );
    Ok(())
}
