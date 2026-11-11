//! Human annotation resolution contract probe.

use std::io::{self, Read};

use agentrouter_evaluation::{AnnotationAdjudication, AnnotationInputItem};
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    item: AnnotationInputItem,
    #[serde(default = "default_label_source")]
    label_source: String,
    #[serde(default)]
    adjudication: Option<AnnotationAdjudication>,
}

fn default_label_source() -> String {
    "generated_candidate".to_owned()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    let needs_adjudication = agentrouter_evaluation::annotation_needs_adjudication(&request.item);
    let result = agentrouter_evaluation::resolve_annotation(
        &request.item,
        &request.label_source,
        request.adjudication.as_ref(),
    );
    println!(
        "{}",
        serde_json::json!({
            "needs_adjudication": needs_adjudication,
            "resolved": result,
        })
    );
    Ok(())
}
