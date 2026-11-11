//! Compatibility probe for Rust observability redaction and safe echo helpers.
//!
//! Reads JSON `{ "redact": ["..."], "echo": [{"text": "...", "limit": 64}] }`
//! from stdin and writes corresponding arrays to stdout.

use std::io::{self, Read};

use serde_json::{json, Value};

fn run() -> Result<(), String> {
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .map_err(|error| error.to_string())?;
    let value: Value = serde_json::from_str(&input).map_err(|error| error.to_string())?;
    let redacted = value
        .get("redact")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .map(|item| {
                    agentrouter_cli::observability::redact(item.as_str().unwrap_or_default())
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let echoed = value
        .get("echo")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .map(|item| {
                    let text = item.get("text").and_then(Value::as_str).unwrap_or_default();
                    let limit = item
                        .get("limit")
                        .and_then(Value::as_u64)
                        .and_then(|number| usize::try_from(number).ok())
                        .unwrap_or(64);
                    agentrouter_cli::observability::safe_echo(text, limit)
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    println!("{}", json!({"redact": redacted, "echo": echoed}));
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
