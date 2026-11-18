//! Offline differential probe for the Rust plugin path and inventory slice.

use std::io::{self, Read};
use std::path::Path;

use serde_json::{json, Value};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;

    let paths = request
        .get("paths")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .map(|entry| {
            let value = entry
                .get("value")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let label = entry
                .get("label")
                .and_then(Value::as_str)
                .unwrap_or("plugin destination");
            match agentrouter_cli::plugins::safe_relative(value, label) {
                Ok(parts) => json!({"accepted": true, "parts": parts}),
                Err(error) => json!({"accepted": false, "error": error}),
            }
        })
        .collect::<Vec<_>>();

    let plugins = request
        .get("plugins")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .map(|entry| {
            let name = entry.as_str().unwrap_or_default();
            match agentrouter_cli::plugins::get_plugin(name) {
                Ok(plugin) => json!({
                    "name": plugin.name,
                    "description": plugin.description,
                    "files": plugin.files.iter().map(|file| json!({"src": file.src, "dest": file.dest})).collect::<Vec<_>>(),
                    "home_subdir": plugin.home_subdir,
                    "cleanup_dirs": plugin.cleanup_dirs,
                }),
                Err(error) => json!({"error": error}),
            }
        })
        .collect::<Vec<_>>();

    let roots = request
        .get("roots")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .map(|entry| {
            let name = entry
                .get("plugin")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let Ok(plugin) = agentrouter_cli::plugins::get_plugin(name) else {
                return json!({"error": "unknown plugin"});
            };
            let override_root = entry
                .get("override")
                .and_then(Value::as_str)
                .filter(|value| !value.is_empty())
                .map(Path::new);
            let home = entry.get("home").and_then(Value::as_str).map(Path::new);
            match agentrouter_cli::plugins::dest_root(plugin, override_root, home) {
                Ok(path) => json!({"path": path}),
                Err(error) => json!({"error": error}),
            }
        })
        .collect::<Vec<_>>();

    println!(
        "{}",
        json!({"paths": paths, "plugins": plugins, "roots": roots})
    );
    Ok(())
}
