//! Offline differential probe for annotation duplicate/leakage checks.

use std::io::{self, Read};

use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    prompts: Vec<String>,
    candidate: Vec<String>,
    reference: Vec<String>,
    threshold: f64,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let normalized: Vec<_> = request
        .prompts
        .iter()
        .map(|prompt| agentrouter_evaluation::annotation_dedup::normalize(prompt))
        .collect();
    let similarities: Vec<_> = request
        .prompts
        .windows(2)
        .map(|pair| agentrouter_evaluation::annotation_dedup::similarity(&pair[0], &pair[1]))
        .collect();
    println!(
        "{}",
        json!({
            "normalized": normalized,
            "similarities": similarities,
            "clusters": agentrouter_evaluation::annotation_dedup::cluster(&request.prompts, request.threshold),
            "leakage": agentrouter_evaluation::annotation_dedup::find_leakage(&request.candidate, &request.reference, request.threshold),
        })
    );
    Ok(())
}
