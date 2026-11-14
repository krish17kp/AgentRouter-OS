use std::io::{self, Read};

use chrono::{Local, NaiveDate};
use serde_json::{json, Value};

fn model_dump(model: agentrouter_registry::ModelEntry) -> Result<Value, serde_json::Error> {
    let mut value = serde_json::to_value(model)?;
    if let Value::Object(fields) = &mut value {
        fields.retain(|_, value| !value.is_null());
    }
    Ok(value)
}

fn models_dump(
    models: Vec<agentrouter_registry::ModelEntry>,
) -> Result<Vec<Value>, serde_json::Error> {
    models.into_iter().map(model_dump).collect()
}

fn request_date(request: &Value) -> Result<NaiveDate, Box<dyn std::error::Error>> {
    match request.get("today").and_then(Value::as_str) {
        Some(value) => Ok(NaiveDate::parse_from_str(value, "%Y-%m-%d")?),
        None => Ok(Local::now().date_naive()),
    }
}

fn optional_match(request: &Value) -> Result<Option<&str>, &'static str> {
    match request.get("match") {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) => Ok(Some(value)),
        Some(_) => Err("match must be a string"),
    }
}

fn run(request: &Value) -> Result<Value, Box<dyn std::error::Error>> {
    let today = request_date(request)?;
    let operation = request
        .get("operation")
        .and_then(Value::as_str)
        .ok_or("operation must be a string")?;
    let value = match operation {
        "map_openrouter" => {
            let raw = request
                .get("raw")
                .ok_or("raw provider object is required")?;
            json!(model_dump(
                agentrouter_registry::refresh::map_openrouter_model_on(raw, today)?
            )?)
        }
        "map_openai" => {
            let raw = request
                .get("raw")
                .ok_or("raw provider object is required")?;
            json!(model_dump(
                agentrouter_registry::refresh::map_openai_model_on(raw, today)?
            )?)
        }
        "openrouter_from_payload" | "openai_from_payload" => {
            let limit = request
                .get("limit")
                .and_then(Value::as_u64)
                .and_then(|value| usize::try_from(value).ok())
                .ok_or("limit must be a non-negative integer")?;
            let match_id = optional_match(request)?;
            let raw = request
                .get("raw")
                .ok_or("raw provider payload is required")?;
            let result = if operation == "openrouter_from_payload" {
                agentrouter_registry::refresh::openrouter_from_payload(raw, limit, match_id, today)?
            } else {
                agentrouter_registry::refresh::openai_from_payload(raw, limit, match_id, today)?
            };
            let (models, warnings) = result;
            json!({"entries": models_dump(models)?, "warnings": warnings})
        }
        "pricing_tier" => {
            let price = request
                .get("prompt_price")
                .and_then(Value::as_f64)
                .ok_or("prompt_price must be a JSON number")?;
            json!(agentrouter_registry::refresh::pricing_tier(price))
        }
        _ => return Err(format!("unknown operation '{operation}'").into()),
    };
    Ok(json!({"value": value}))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let result = run(&request)?;
    println!("{}", serde_json::to_string(&result)?);
    Ok(())
}
