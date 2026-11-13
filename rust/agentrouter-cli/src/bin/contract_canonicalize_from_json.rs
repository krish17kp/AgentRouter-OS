//! Offline differential probe for Python/Rust OpenAPI canonicalization.

use std::io::{self, Read};

use serde_json::Value;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let mut value: Value = serde_json::from_str(&input)?;
    agentrouter_cli::contract::canonicalize(&mut value);
    print!("{}", agentrouter_cli::contract::dumps(&value)?);
    Ok(())
}
