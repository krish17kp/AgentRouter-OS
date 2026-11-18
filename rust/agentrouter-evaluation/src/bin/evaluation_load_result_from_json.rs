//! Offline fixture probe for loading versioned evaluation result JSON.

use serde::Deserialize;
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Deserialize)]
struct Input {
    path: PathBuf,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    println!(
        "{}",
        serde_json::to_string(&agentrouter_evaluation::load_result(&input.path)?)?
    );
    Ok(())
}
