//! Offline probe for blinded annotation pack operations.

use std::io::{self, Read};

use agentrouter_evaluation::annotation_packs::{
    adjudication_candidates, build_pack, disagreement_items, labels_to_csv, merge_by_candidate,
    pending, progress,
};
use agentrouter_evaluation::annotation_schema::{Candidate, ItemLabels};
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    operation: String,
    #[serde(default)]
    candidates: Vec<Candidate>,
    #[serde(default)]
    done: Vec<ItemLabels>,
    #[serde(default = "zero_seed")]
    seed: String,
    #[serde(default)]
    label_sets: Vec<Vec<ItemLabels>>,
}

fn zero_seed() -> String {
    "0".to_owned()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    match request.operation.as_str() {
        "build_pack" => {
            println!(
                "{}",
                serde_json::to_string(&build_pack(&request.candidates, &request.seed,)?)?
            );
        }
        "pending" => println!(
            "{}",
            serde_json::to_string(&pending(&request.candidates, &request.done))?
        ),
        "progress" => {
            let (total, done, remaining) = progress(&request.candidates, &request.done);
            println!(
                "{}",
                json!({"total": total, "done": done, "remaining": remaining})
            );
        }
        "merge" => println!(
            "{}",
            serde_json::to_string(&merge_by_candidate(&request.label_sets))?
        ),
        "disagreements" => println!(
            "{}",
            serde_json::to_string(&disagreement_items(&request.label_sets))?
        ),
        "adjudication_candidates" => println!(
            "{}",
            serde_json::to_string(&adjudication_candidates(&request.label_sets))?
        ),
        "csv" => println!("{}", serde_json::to_string(&labels_to_csv(&request.done))?),
        other => return Err(format!("unknown annotation pack operation '{other}'").into()),
    }
    Ok(())
}
