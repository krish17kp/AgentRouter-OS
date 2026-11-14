use std::io::{self, Read};

use agentrouter_registry::{ExecutionTarget, Provider};
use serde_json::{json, Value};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let kind = request
        .get("kind")
        .and_then(Value::as_str)
        .ok_or("kind must be a string")?;
    let value = request.get("value").cloned().ok_or("value is required")?;
    let output = match kind {
        "execution_target" => {
            serde_json::to_value(serde_json::from_value::<ExecutionTarget>(value)?)?
        }
        "provider" => serde_json::to_value(serde_json::from_value::<Provider>(value)?)?,
        _ => return Err(format!("unknown schema kind: {kind}").into()),
    };
    println!("{}", json!(output));
    Ok(())
}
