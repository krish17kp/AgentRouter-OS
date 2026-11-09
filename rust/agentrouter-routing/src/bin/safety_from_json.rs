//! JSON probe for safety-gate differential tests; execution is not exposed.
use agentrouter_core::Classification;
use agentrouter_routing::safety::gates_for;
use std::io::{self, Read};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let classification: Classification = serde_json::from_str(&input)?;
    println!("{}", serde_json::to_string(&gates_for(&classification))?);
    Ok(())
}
