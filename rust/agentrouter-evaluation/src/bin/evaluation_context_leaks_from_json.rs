use std::io::{self, Read};

use agentrouter_evaluation::context_bands::{cross_split_leaks, ContextBandCase};
use serde::Deserialize;

#[derive(Deserialize)]
struct Request {
    holdout: Vec<ContextBandCase>,
    references: serde_json::Value,
    #[serde(default)]
    comparisons: Vec<[String; 2]>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let references = request
        .references
        .as_object()
        .ok_or("references must be a JSON object")?
        .iter()
        .map(|(source, prompts)| {
            Ok((
                source.clone(),
                serde_json::from_value::<Vec<String>>(prompts.clone())?,
            ))
        })
        .collect::<Result<Vec<_>, serde_json::Error>>()?;
    let similarities = request
        .comparisons
        .iter()
        .map(|pair| agentrouter_evaluation::context_bands::prompt_similarity(&pair[0], &pair[1]))
        .collect::<Vec<_>>();
    println!(
        "{}",
        serde_json::to_string(&serde_json::json!({
            "leaks": cross_split_leaks(&request.holdout, &references),
            "similarities": similarities,
        }))?
    );
    Ok(())
}
