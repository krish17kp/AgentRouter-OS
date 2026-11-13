//! Offline differential probe for the Rust OpenAPI operation-surface diff.

use std::io::{self, Read};

use serde_json::Value;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let old = request
        .get("old")
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "old document is required"))?;
    let new = request
        .get("new")
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "new document is required"))?;
    println!(
        "{}",
        serde_json::to_string(&agentrouter_cli::contract::diff_contracts_surface(old, new))?
    );
    Ok(())
}
