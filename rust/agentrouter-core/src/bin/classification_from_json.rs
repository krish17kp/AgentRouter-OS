use std::io::{self, Read};

use agentrouter_core::Classification;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let classification: Classification = serde_json::from_str(&input)?;
    println!("{}", serde_json::to_string(&classification)?);
    Ok(())
}
