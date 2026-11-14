use std::io::{self, Read};
use std::path::PathBuf;

use agentrouter_api::schemas::{ClassifyRequest, DryRunRequest, FeedbackRequest, RouteRequest};
use agentrouter_api::service;
use serde_json::Value;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let envelope: Value = serde_json::from_str(&input)?;
    let kind = envelope["kind"].as_str().ok_or("kind must be a string")?;
    let home = PathBuf::from(envelope["home"].as_str().ok_or("home must be a string")?);
    let request = &envelope["request"];
    let value = match kind {
        "list_models" => serde_json::to_value(service::list_models(&home)?)?,
        "list_hosts" => serde_json::to_value(service::list_hosts())?,
        "classify" => {
            let parsed: ClassifyRequest = serde_json::from_value(request.clone())?;
            service::classify_task(&parsed)?
        }
        "route" => {
            let parsed: RouteRequest = serde_json::from_value(request.clone())?;
            service::route_task(&home, &parsed)?
        }
        "decision" => {
            let decision_id = request["decision_id"]
                .as_str()
                .ok_or("decision_id must be a string")?;
            service::get_decision(&home, decision_id)?.unwrap_or(Value::Null)
        }
        "feedback" => {
            let parsed: FeedbackRequest = serde_json::from_value(request.clone())?;
            Value::Bool(service::save_feedback(&home, &parsed)?)
        }
        "dry_run" => {
            let parsed: DryRunRequest = serde_json::from_value(request.clone())?;
            service::execute_dry_run(&home, &parsed)?.unwrap_or(Value::Null)
        }
        _ => return Err("unknown service operation".into()),
    };
    println!("{}", serde_json::to_string(&value)?);
    Ok(())
}
