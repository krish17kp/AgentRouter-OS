//! Offline probe for annotation artifact storage and canonical split hashes.

use std::io::{self, Read};
use std::path::PathBuf;

use agentrouter_evaluation::annotation_schema::{
    AdjudicatedItem, Candidate, DatasetManifest, ItemLabels,
};
use agentrouter_evaluation::annotation_store as store;
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    operation: String,
    path: PathBuf,
    #[serde(default)]
    candidates: Vec<Candidate>,
    #[serde(default)]
    labels: Vec<ItemLabels>,
    #[serde(default)]
    items: Vec<AdjudicatedItem>,
    #[serde(default)]
    manifest: Option<DatasetManifest>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    match request.operation.as_str() {
        "split_sha256" => println!(
            "{}",
            json!({"sha256": store::split_sha256(&request.items)?})
        ),
        "save_candidates" => {
            store::save_candidates(&request.path, &request.candidates)?;
            println!("{{\"ok\":true}}");
        }
        "load_candidates" => println!(
            "{}",
            serde_json::to_string(&store::load_candidates(&request.path)?)?
        ),
        "save_labels" => {
            store::save_labels(&request.path, &request.labels)?;
            println!("{{\"ok\":true}}");
        }
        "load_labels" => println!(
            "{}",
            serde_json::to_string(&store::load_labels(&request.path)?)?
        ),
        "save_dataset" => {
            store::save_dataset(&request.path, &request.items)?;
            println!("{{\"ok\":true}}");
        }
        "load_dataset" => println!(
            "{}",
            serde_json::to_string(&store::load_dataset(&request.path)?)?
        ),
        "save_manifest" => {
            let manifest = request.manifest.as_ref().ok_or("manifest is required")?;
            store::save_manifest(&request.path, manifest)?;
            println!("{{\"ok\":true}}");
        }
        "load_manifest" => println!(
            "{}",
            serde_json::to_string(&store::load_manifest(&request.path)?)?
        ),
        other => return Err(format!("unknown annotation store operation '{other}'").into()),
    }
    Ok(())
}
