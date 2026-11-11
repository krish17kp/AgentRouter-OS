//! Offline differential probe for LLMRouterBench adapter behavior.

use serde::Deserialize;
use serde_json::json;
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    path: PathBuf,
    metadata: agentrouter_evaluation::EvaluationDatasetMetadata,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let metadata = &input.metadata;
    let cases = match agentrouter_evaluation::load_adapter_fixture(&input.path, metadata) {
        Ok(cases) => cases,
        Err(error) => {
            println!("{}", json!({"error": error}));
            return Ok(());
        }
    };
    let (real_available, real_reason) =
        agentrouter_evaluation::adapter_real_availability(&metadata.name, None);
    println!(
        "{}",
        json!({
            "metadata": metadata,
            "availability": agentrouter_evaluation::adapter_availability(&input.path),
            "real_available": real_available,
            "real_reason": real_reason,
            "describe": agentrouter_evaluation::llmrouterbench_describe(&input.path, metadata),
            "model_mapping_required": true,
            "model_mapping_note": "Provide a model-mapping file translating LLMRouterBench model keys to registry entries; commercial names never appear in routing logic.",
            "full_run_status": agentrouter_evaluation::llmrouterbench_full_run_status(),
            "cases": cases,
            "sample": agentrouter_evaluation::sample_adapter_cases(&cases, Some(4), 3),
            "checksum": agentrouter_evaluation::adapter_checksum(&cases),
            "real_error": format!("{}: {}", metadata.name, real_reason),
        })
    );
    Ok(())
}
