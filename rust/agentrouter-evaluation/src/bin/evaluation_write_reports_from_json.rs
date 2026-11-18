//! Offline fixture probe for Python/Rust evaluation report directory parity.

use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
struct Input {
    result: serde_json::Value,
    out_dir: std::path::PathBuf,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let files = agentrouter_evaluation::write_reports(&input.result, &input.out_dir)?;
    println!("{}", serde_json::to_string(&files)?);
    Ok(())
}
