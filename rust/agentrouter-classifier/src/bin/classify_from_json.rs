//! Parse a task and explicit classifier overrides from JSON stdin.
use std::io::{self, Read};

use agentrouter_classifier::{classify, ClassifyOptions};
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    task: String,
    #[serde(default)]
    overrides: ClassifyOptions,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    if request.task.trim().is_empty() {
        return Err("task must be nonempty".into());
    }
    let result = classify(&request.task, &request.overrides);
    println!("{}", serde_json::to_string(&result)?);
    Ok(())
}
