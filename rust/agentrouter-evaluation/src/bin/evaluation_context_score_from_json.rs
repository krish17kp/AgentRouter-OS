use std::cell::Cell;
use std::io::{self, Read};

use agentrouter_core::ContextBand;
use agentrouter_evaluation::context_bands::{score, ContextBandCase};
use serde::Deserialize;

#[derive(Deserialize)]
struct Request {
    cases: Vec<ContextBandCase>,
    predictions: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    if request.cases.len() != request.predictions.len() {
        return Err("predictions length must match cases".into());
    }
    let predictions = request
        .predictions
        .iter()
        .map(|prediction| match prediction.as_str() {
            "small" => Ok(ContextBand::Small),
            "medium" => Ok(ContextBand::Medium),
            "large" => Ok(ContextBand::Large),
            _ => Err(format!("unknown context band prediction: {prediction}")),
        })
        .collect::<Result<Vec<_>, _>>()?;
    let index = Cell::new(0);
    let report = score(&request.cases, |_| {
        let current = index.get();
        index.set(current + 1);
        predictions[current]
    })
    .map_err(io::Error::other)?;
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
