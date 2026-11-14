//! Offline annotation artifact schema probe.

use std::io::{self, Read};

use agentrouter_evaluation::annotation_schema::{
    AdjudicatedItem, AnnotatorLabel, Candidate, DatasetManifest, ItemLabels,
};
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    model: String,
    value: serde_json::Value,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    match request.model.as_str() {
        "candidate" => {
            let value: Candidate = serde_json::from_value(request.value)?;
            value.validate()?;
            println!("{}", json!({ "value": value }));
        }
        "annotator_label" => {
            let value: AnnotatorLabel = serde_json::from_value(request.value)?;
            value.validate()?;
            println!("{}", json!({ "value": value }));
        }
        "item_labels" => {
            let value: ItemLabels = serde_json::from_value(request.value)?;
            value.validate()?;
            println!(
                "{}",
                json!({
                    "value": value,
                    "annotators": value.annotators(),
                    "agrees": value.agrees(),
                })
            );
        }
        "adjudicated_item" => {
            let value: AdjudicatedItem = serde_json::from_value(request.value)?;
            value.validate()?;
            println!("{}", json!({ "value": value }));
        }
        "dataset_manifest" => {
            let value: DatasetManifest = serde_json::from_value(request.value)?;
            println!("{}", json!({ "value": value }));
        }
        other => return Err(format!("unknown annotation schema model '{other}'").into()),
    }
    Ok(())
}
