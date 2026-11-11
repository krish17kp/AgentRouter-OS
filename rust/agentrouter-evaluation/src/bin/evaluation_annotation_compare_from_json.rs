use std::io::{self, Read};

use agentrouter_evaluation::annotation_compare::{compare_all, DEFAULT_HYBRID_THRESHOLD};
use agentrouter_evaluation::annotation_schema::AdjudicatedItem;
use serde::Deserialize;

#[derive(Deserialize)]
struct Request {
    items: Vec<AdjudicatedItem>,
    #[serde(default = "default_threshold")]
    threshold: f64,
}

fn default_threshold() -> f64 {
    DEFAULT_HYBRID_THRESHOLD
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    for item in &request.items {
        item.validate()?;
    }
    let result = compare_all(&request.items, request.threshold)?;
    println!("{}", serde_json::to_string(&result)?);
    Ok(())
}
