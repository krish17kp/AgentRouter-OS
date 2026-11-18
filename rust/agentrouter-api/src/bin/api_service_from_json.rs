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
    if kind == "home" {
        println!("{}", serde_json::to_string(&service::home())?);
        return Ok(());
    }
    let home = PathBuf::from(envelope["home"].as_str().ok_or("home must be a string")?);
    let request = &envelope["request"];
    let value = match kind {
        "list_models" => serde_json::to_value(service::list_models(&home)?)?,
        "load_registry" => serde_json::to_value(service::load_registry()?)?,
        "list_hosts" => serde_json::to_value(service::list_hosts())?,
        "classify" => {
            let parsed: ClassifyRequest = serde_json::from_value(request.clone())?;
            service::classify_task(&parsed)?
        }
        "classify_args" => service::classify_task_args(
            request["task"].as_str().ok_or("task must be a string")?,
            request
                .get("context_tokens")
                .filter(|value| !value.is_null())
                .map(|value| {
                    value
                        .as_number()
                        .cloned()
                        .ok_or("context_tokens must be an integer")
                })
                .transpose()?,
            request.get("risk").and_then(Value::as_str),
            request
                .get("tools")
                .filter(|value| !value.is_null())
                .map(|value| serde_json::from_value::<Vec<String>>(value.clone()))
                .transpose()?,
        )?,
        "route" => {
            let parsed: RouteRequest = serde_json::from_value(request.clone())?;
            service::route_task(&home, &parsed)?
        }
        "route_args" => service::route_task_args(
            &home,
            request["task"].as_str().ok_or("task must be a string")?,
            request.get("prefer").and_then(Value::as_str),
            request
                .get("context_tokens")
                .filter(|value| !value.is_null())
                .map(|value| {
                    value
                        .as_number()
                        .cloned()
                        .ok_or("context_tokens must be an integer")
                })
                .transpose()?,
            request.get("risk").and_then(Value::as_str),
            request
                .get("tools")
                .filter(|value| !value.is_null())
                .map(|value| serde_json::from_value::<Vec<String>>(value.clone()))
                .transpose()?,
            request
                .get("no_log")
                .and_then(Value::as_bool)
                .unwrap_or(false),
        )?,
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
