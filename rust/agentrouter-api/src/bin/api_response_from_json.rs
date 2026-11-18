use std::io::{self, Read};

use agentrouter_api::responses::{
    ClassifyResponse, DecisionResponse, DryRunResponse, ErrorResponse, FeedbackResponse,
    HealthResponse, HostStatusResponse, ModelSummary, RouteResponse,
};
use serde::de::DeserializeOwned;
use serde_json::Value;

fn roundtrip<T: DeserializeOwned + serde::Serialize>(
    value: &Value,
) -> Result<Value, Box<dyn std::error::Error>> {
    Ok(serde_json::to_value(serde_json::from_value::<T>(
        value.clone(),
    )?)?)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let envelope: Value = serde_json::from_str(&input)?;
    let kind = envelope["kind"].as_str().ok_or("kind must be a string")?;
    let response = &envelope["response"];
    let value = match kind {
        "error" => roundtrip::<ErrorResponse>(response)?,
        "health" => roundtrip::<HealthResponse>(response)?,
        "model" => roundtrip::<ModelSummary>(response)?,
        "host" => roundtrip::<HostStatusResponse>(response)?,
        "feedback" => roundtrip::<FeedbackResponse>(response)?,
        "classify" => roundtrip::<ClassifyResponse>(response)?,
        "route" => roundtrip::<RouteResponse>(response)?,
        "decision" => roundtrip::<DecisionResponse>(response)?,
        "dry_run" => roundtrip::<DryRunResponse>(response)?,
        _ => return Err("unknown response kind".into()),
    };
    println!("{}", serde_json::to_string(&value)?);
    Ok(())
}
