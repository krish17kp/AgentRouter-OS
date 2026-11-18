//! Offline fixture probe for Python/Rust evaluation comparison parity.

use serde::Deserialize;
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Deserialize)]
struct Input {
    baseline: serde_json::Value,
    current: serde_json::Value,
    out_dir: PathBuf,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let comparison = agentrouter_evaluation::compare_results(&input.baseline, &input.current);
    let files = agentrouter_evaluation::write_comparison(&comparison, &input.out_dir)?;
    println!(
        "{}",
        serde_json::json!({"comparison": comparison, "files": files})
    );
    Ok(())
}
