//! Offline probe for the shared fixture-backed evaluation adapter contract.

use agentrouter_evaluation::{
    adapter_availability, adapter_checksum, adapter_real_availability, describe_adapter,
    load_adapter_dataset, sample_adapter_cases, EvaluationDatasetMetadata,
};
use serde::Deserialize;
use serde_json::json;
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    path: PathBuf,
    metadata: EvaluationDatasetMetadata,
    hf_repo: Option<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let cases = match load_adapter_dataset(
        &input.path,
        &input.metadata,
        input.hf_repo.as_deref(),
        "fixture",
    ) {
        Ok(cases) => cases,
        Err(error) => {
            println!("{}", serde_json::to_string(&json!({"error": error}))?);
            return Ok(());
        }
    };
    let (real_available, real_reason) =
        adapter_real_availability(&input.metadata.name, input.hf_repo.as_deref());
    let real_load = load_adapter_dataset(
        &input.path,
        &input.metadata,
        input.hf_repo.as_deref(),
        "real",
    );
    let real_error = real_load.err();
    let sampled = sample_adapter_cases(&cases, Some(4), 3);
    println!(
        "{}",
        serde_json::to_string(&json!({
            "metadata": input.metadata.clone(),
            "availability": adapter_availability(&input.path),
            "real_available": real_available,
            "real_reason": real_reason,
            "describe": describe_adapter(&input.path, &input.metadata, input.hf_repo.as_deref()),
            "cases": cases,
            "sample": sampled,
            "checksum": adapter_checksum(&cases),
            "real_error": real_error,
        }))?
    );
    Ok(())
}
