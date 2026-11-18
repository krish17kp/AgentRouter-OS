//! Offline probe for Rust OpenAPI canonical export and provenance.

use std::io::{self, Read};
use std::path::PathBuf;

use serde_json::{json, Value};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let root = request
        .get("root")
        .and_then(Value::as_str)
        .ok_or("root path is required")?;
    let document = request
        .get("document")
        .ok_or("OpenAPI document is required")?;
    let generated_at = request.get("generated_at").and_then(Value::as_str);
    let (path, canonical) =
        agentrouter_cli::contract::export_contract(&PathBuf::from(root), document, generated_at)
            .map_err(io::Error::other)?;
    println!(
        "{}",
        serde_json::to_string(&json!({"path": path, "document": canonical}))?
    );
    Ok(())
}
