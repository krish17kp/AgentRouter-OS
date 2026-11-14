use std::io::{self, Read};

use agentrouter_core::{ApprovalLevel, ContextBand, Level, OutputType, TaskType};
use agentrouter_registry::{
    AbilitySource, DeprecationStatus, ExecutionMode, ExecutionTarget, LatencyTier, PricingTier,
    Provider, ReleaseChannel, SnapshotType,
};
use serde::de::DeserializeOwned;
use serde_json::{json, Value};

fn roundtrip<T>(value: Value) -> Result<Value, Box<dyn std::error::Error>>
where
    T: DeserializeOwned + serde::Serialize,
{
    Ok(serde_json::to_value(serde_json::from_value::<T>(value)?)?)
}

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
        "task_type" => roundtrip::<TaskType>(value)?,
        "level" => roundtrip::<Level>(value)?,
        "output_type" => roundtrip::<OutputType>(value)?,
        "approval_level" => roundtrip::<ApprovalLevel>(value)?,
        "context_band" => roundtrip::<ContextBand>(value)?,
        "pricing_tier" => roundtrip::<PricingTier>(value)?,
        "latency_tier" => roundtrip::<LatencyTier>(value)?,
        "deprecation_status" => roundtrip::<DeprecationStatus>(value)?,
        "release_channel" => roundtrip::<ReleaseChannel>(value)?,
        "snapshot_type" => roundtrip::<SnapshotType>(value)?,
        "ability_source" => roundtrip::<AbilitySource>(value)?,
        "execution_mode" => roundtrip::<ExecutionMode>(value)?,
        _ => return Err(format!("unknown schema kind: {kind}").into()),
    };
    println!("{}", json!(output));
    Ok(())
}
