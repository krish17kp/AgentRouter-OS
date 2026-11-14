//! JSON compatibility bridge for the synchronous Rust SDK client.

use std::io::{self, Read};
use std::time::Duration;

use agentrouter_cli::sdk::{AgentRouterClient, ClientError};
use serde_json::{json, Value};

fn result(value: Result<Value, ClientError>) -> Value {
    match value {
        Ok(value) => json!({"ok": value}),
        Err(ClientError::Api(error)) => json!({
            "error": {
                "status_code": error.status_code,
                "code": error.code,
                "display": error.to_string(),
            }
        }),
        Err(ClientError::Transport(_)) => json!({"transport_error": "transport failure"}),
    }
}

fn call(client: &AgentRouterClient, operation: &Value) -> Value {
    let name = operation
        .get("name")
        .and_then(Value::as_str)
        .unwrap_or_default();
    match name {
        "health" => result(client.health()),
        "ready" => result(client.ready()),
        "models" => result(client.models().map(Value::Array)),
        "hosts" => result(client.hosts().map(Value::Array)),
        "classify" => {
            let task = operation
                .get("task")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let context_tokens = operation
                .get("context_tokens")
                .and_then(Value::as_number)
                .cloned();
            let risk = operation.get("risk").and_then(Value::as_str);
            let tools = operation
                .get("tools")
                .and_then(Value::as_array)
                .map(|values| {
                    values
                        .iter()
                        .filter_map(Value::as_str)
                        .map(str::to_owned)
                        .collect::<Vec<_>>()
                });
            result(client.classify(task, context_tokens, risk, tools.as_deref()))
        }
        "route" => {
            let task = operation
                .get("task")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let prefer = operation.get("prefer").and_then(Value::as_str);
            let context_tokens = operation
                .get("context_tokens")
                .and_then(Value::as_number)
                .cloned();
            let risk = operation.get("risk").and_then(Value::as_str);
            let tools = operation
                .get("tools")
                .and_then(Value::as_array)
                .map(|values| {
                    values
                        .iter()
                        .filter_map(Value::as_str)
                        .map(str::to_owned)
                        .collect::<Vec<_>>()
                });
            let no_log = operation
                .get("no_log")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            result(client.route(task, prefer, context_tokens, risk, tools.as_deref(), no_log))
        }
        "get_decision" => {
            let id = operation
                .get("decision_id")
                .and_then(Value::as_str)
                .unwrap_or_default();
            result(client.get_decision(id))
        }
        "feedback" => {
            let id = operation
                .get("decision_id")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let rating = operation
                .get("rating")
                .and_then(Value::as_i64)
                .unwrap_or_default();
            let note = operation.get("note").and_then(Value::as_str);
            result(client.feedback(id, rating, note))
        }
        "execute_dry_run" => {
            let id = operation
                .get("decision_id")
                .and_then(Value::as_str)
                .unwrap_or_default();
            result(client.execute_dry_run(id))
        }
        _ => json!({"bridge_error": format!("unknown operation '{name}'")}),
    }
}

fn run(request: &Value) -> Result<Value, Box<dyn std::error::Error>> {
    let base_url = request
        .get("base_url")
        .and_then(Value::as_str)
        .ok_or("base_url must be a string")?;
    let api_key = request.get("api_key").and_then(Value::as_str);
    let timeout_seconds = request
        .get("timeout_seconds")
        .and_then(Value::as_f64)
        .unwrap_or(10.0);
    if !timeout_seconds.is_finite() || timeout_seconds <= 0.0 {
        return Err("timeout_seconds must be finite and positive".into());
    }
    let client = AgentRouterClient::new(
        Some(base_url),
        api_key,
        Some(Duration::from_secs_f64(timeout_seconds)),
    );
    let operations = request
        .get("operations")
        .and_then(Value::as_array)
        .ok_or("operations must be an array")?;
    Ok(Value::Array(
        operations
            .iter()
            .map(|operation| call(&client, operation))
            .collect(),
    ))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    println!("{}", serde_json::to_string(&run(&request)?)?);
    Ok(())
}
