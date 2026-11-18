//! Offline differential probe for plugin ownership-state validation.

use std::io::{self, Read};

use serde_json::{json, Value};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let states = request
        .get("states")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .map(|entry| {
            let name = entry
                .get("plugin")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let Ok(plugin) = agentrouter_cli::plugins::get_plugin(name) else {
                return json!({"accepted": false, "error": "unknown plugin"});
            };
            let parsed = entry
                .get("state_raw")
                .and_then(Value::as_str)
                .map(serde_json::from_str::<Value>)
                .transpose();
            match parsed {
                Err(_) => json!({"accepted": false, "error": "invalid JSON"}),
                Ok(Some(state)) => {
                    match agentrouter_cli::plugins::validate_state_data(plugin, &state) {
                        Ok(()) => json!({"accepted": true}),
                        Err(error) => json!({"accepted": false, "error": error}),
                    }
                }
                Ok(None) => json!({"accepted": false, "error": "state is required"}),
            }
        })
        .collect::<Vec<_>>();
    let reads = request
        .get("reads")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .map(|entry| {
            let name = entry
                .get("plugin")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let Ok(plugin) = agentrouter_cli::plugins::get_plugin(name) else {
                return json!({"accepted": false, "error": "unknown plugin"});
            };
            let Some(root) = entry.get("root").and_then(Value::as_str) else {
                return json!({"accepted": false, "error": "root is required"});
            };
            match agentrouter_cli::plugins::read_state(std::path::Path::new(root), plugin) {
                Ok(Some(state)) => json!({
                    "accepted": true,
                    "state": state.value,
                    "sha256": state.sha256
                }),
                Ok(None) => json!({"accepted": true, "state": null, "sha256": null}),
                Err(error) => json!({"accepted": false, "error": error}),
            }
        })
        .collect::<Vec<_>>();
    println!("{}", json!({"states": states, "reads": reads}));
    Ok(())
}
