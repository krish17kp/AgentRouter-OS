//! Offline fixture probe for deterministic sample parity.

use std::io::{self, Read};

use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    items: Vec<String>,
    limit: i64,
    seed: i64,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let sample = agentrouter_evaluation::deterministic_sample(
        &request.items,
        request.limit,
        request.seed,
        |item| item.clone(),
    );
    println!("{}", serde_json::to_string(&sample)?);
    Ok(())
}
