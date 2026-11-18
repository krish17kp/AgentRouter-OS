use std::io::{self, Read};

use agentrouter_api::schemas::{
    ClassifyRequest, DryRunRequest, FeedbackRequest, RouteRequest, MAX_DECISION_ID_CHARS,
    MAX_NOTE_CHARS, MAX_PREFER_CHARS, MAX_TASK_CHARS, MAX_TOOLS, MAX_TOOL_NAME_CHARS,
};
use serde_json::Value;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let envelope: Value = serde_json::from_str(&input)?;
    let kind = envelope["kind"].as_str().ok_or("kind must be a string")?;
    let request = &envelope["request"];
    let value = match kind {
        "classify" => {
            let parsed: ClassifyRequest = serde_json::from_value(request.clone())?;
            parsed.validate()?;
            serde_json::to_value(parsed)?
        }
        "route" => {
            let parsed: RouteRequest = serde_json::from_value(request.clone())?;
            parsed.validate()?;
            serde_json::to_value(parsed)?
        }
        "feedback" => {
            let parsed: FeedbackRequest = serde_json::from_value(request.clone())?;
            parsed.validate()?;
            serde_json::to_value(parsed)?
        }
        "dry_run" => {
            let parsed: DryRunRequest = serde_json::from_value(request.clone())?;
            parsed.validate()?;
            serde_json::to_value(parsed)?
        }
        "constants" => serde_json::json!({
            "MAX_TASK_CHARS": MAX_TASK_CHARS,
            "MAX_NOTE_CHARS": MAX_NOTE_CHARS,
            "MAX_TOOLS": MAX_TOOLS,
            "MAX_TOOL_NAME_CHARS": MAX_TOOL_NAME_CHARS,
            "MAX_DECISION_ID_CHARS": MAX_DECISION_ID_CHARS,
            "MAX_PREFER_CHARS": MAX_PREFER_CHARS,
        }),
        _ => return Err("unknown request kind".into()),
    };
    println!("{}", serde_json::to_string(&value)?);
    Ok(())
}
