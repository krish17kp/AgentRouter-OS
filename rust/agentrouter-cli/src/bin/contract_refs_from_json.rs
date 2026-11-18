//! Offline differential probe for Python/Rust OpenAPI `$ref` validation.

use std::io::{self, Read};

use serde_json::Value;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let document: Value = serde_json::from_str(&input)?;
    let invalid = agentrouter_cli::contract::validate_refs(&document)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
    println!("{}", serde_json::to_string(&invalid)?);
    Ok(())
}
