//! Offline differential probe for the Python/Rust dashboard renderer.

use std::io::{self, Read};

use serde_json::Value;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let stats = request
        .get("stats")
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "stats is required"))?;
    let recent = request
        .get("recent")
        .and_then(Value::as_array)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "recent must be an array"))?;
    print!("{}", agentrouter_cli::dashboard::render_html(stats, recent));
    Ok(())
}
