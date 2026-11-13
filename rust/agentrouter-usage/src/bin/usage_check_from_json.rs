//! Offline fixture probe for Python/Rust `check_usage` contract tests.

use std::io::Read;
use std::time::Duration;

use agentrouter_usage::{check_usage, register_live_check, UsageStatus};
use serde_json::Value;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let provider = request
        .get("provider")
        .and_then(Value::as_str)
        .unwrap_or("fixture-provider")
        .to_owned();
    let live = request
        .get("live")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let timeout = request
        .get("timeout_seconds")
        .and_then(Value::as_f64)
        .unwrap_or(5.0);

    if let Some(value) = request.get("adapter") {
        let fixture: UsageStatus = serde_json::from_value(value.clone())?;
        let result = fixture.clone();
        register_live_check(&provider, move |_timeout| result.clone());
    }

    let status = check_usage(&provider, live, Duration::from_secs_f64(timeout));
    println!("{}", serde_json::to_string(&status)?);
    Ok(())
}
