//! Offline fixture probe for Markdown evaluation report parity.

use std::io::{self, Read};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let result: serde_json::Value = serde_json::from_str(&input)?;
    print!("{}", agentrouter_evaluation::render_markdown(&result));
    Ok(())
}
