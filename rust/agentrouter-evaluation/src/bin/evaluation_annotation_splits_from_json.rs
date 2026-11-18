//! Offline differential probe for deterministic annotation splits.

use std::collections::BTreeMap;
use std::io::{self, Read};

use serde::Deserialize;
use serde_json::Value;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    items: Vec<Value>,
    #[serde(default)]
    frozen_holdout_prompts: Vec<String>,
    #[serde(default)]
    ratios: Option<BTreeMap<String, f64>>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    match agentrouter_evaluation::annotation_splits::partition(
        &request.items,
        &request.frozen_holdout_prompts,
        request.ratios.as_ref(),
    ) {
        Ok(result) => println!("{}", result),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(3);
        }
    }
    Ok(())
}
