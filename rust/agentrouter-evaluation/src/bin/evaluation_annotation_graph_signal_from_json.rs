//! Offline probe for annotation repository-impact signal parity.

use std::io::{self, Read};

use agentrouter_evaluation::annotation_graph_signals::{impact_for, impact_for_default};
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    prompt: String,
    #[serde(default)]
    graph_path: Option<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let signal = match request.graph_path {
        Some(path) => impact_for(&request.prompt, path),
        None => impact_for_default(&request.prompt),
    }
    .map_err(io::Error::other)?;
    println!("{}", serde_json::to_string(&signal)?);
    Ok(())
}
