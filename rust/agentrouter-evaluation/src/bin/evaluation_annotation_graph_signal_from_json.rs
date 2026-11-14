//! Offline probe for annotation repository-impact signal parity.

use std::io::{self, Read};

use agentrouter_evaluation::annotation_graph_signals::{impact_for, impact_for_default};
use serde::Deserialize;
use serde_json::Value;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    #[serde(default)]
    prompt: Option<String>,
    #[serde(default)]
    graph_path: Option<String>,
    #[serde(default)]
    sequence: Vec<SequenceEntry>,
}

#[derive(Deserialize)]
struct SequenceEntry {
    prompt: String,
    graph_path: String,
    #[serde(default)]
    write_graph: Option<Value>,
}

fn calculate(
    prompt: &str,
    path: Option<&str>,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let signal = match path {
        Some(path) => impact_for(prompt, path),
        None => impact_for_default(prompt),
    }
    .map_err(io::Error::other)?;
    Ok(serde_json::to_value(signal)?)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    if !request.sequence.is_empty() {
        let mut signals = Vec::with_capacity(request.sequence.len());
        for entry in request.sequence {
            if let Some(graph) = entry.write_graph {
                std::fs::write(&entry.graph_path, serde_json::to_vec(&graph)?)?;
            }
            signals.push(calculate(&entry.prompt, Some(&entry.graph_path))?);
        }
        println!("{}", serde_json::to_string(&signals)?);
    } else {
        let prompt = request.prompt.as_deref().ok_or("prompt is required")?;
        println!(
            "{}",
            serde_json::to_string(&calculate(prompt, request.graph_path.as_deref())?)?
        );
    }
    Ok(())
}
