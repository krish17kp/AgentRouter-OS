//! Offline probe for deterministic annotation candidate generation.

use std::io::{self, Read};

use agentrouter_evaluation::annotation_candidates::{candidate_bank, generate};
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    operation: String,
    #[serde(default)]
    count: Option<i64>,
    #[serde(default = "default_seed")]
    seed: String,
}

fn default_seed() -> String {
    "20260731".to_owned()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    match request.operation.as_str() {
        "bank" => println!("{}", serde_json::to_string(&candidate_bank()?)?),
        "generate" => println!(
            "{}",
            serde_json::to_string(&generate(request.count, &request.seed)?)?
        ),
        other => return Err(format!("unknown annotation candidate operation '{other}'").into()),
    }
    Ok(())
}
