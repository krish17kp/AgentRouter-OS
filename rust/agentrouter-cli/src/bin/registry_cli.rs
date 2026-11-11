//! Compatibility probe for `agentrouter registry list`.
//!
//! Usage: registry_cli <home> [--provider <id>] [--active-only] [--json]

use std::path::PathBuf;

use agentrouter_registry::{load_all_models, load_providers, DeprecationStatus, ModelEntry};
use serde_json::Value;

fn parse_options(
    args: impl IntoIterator<Item = String>,
) -> Result<(Option<String>, bool, bool), String> {
    let mut args = args.into_iter();
    let mut provider = None;
    let mut active_only = false;
    let mut json_output = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--provider" => {
                let value = args.next().ok_or("--provider needs a value")?;
                if value.starts_with('-') {
                    return Err("--provider needs a value".to_string());
                }
                provider = Some(value);
            }
            "--active-only" => active_only = true,
            "--json" => json_output = true,
            _ => return Err(format!("unknown option {arg}")),
        }
    }
    Ok((provider, active_only, json_output))
}

fn model_json(model: &ModelEntry) -> Result<Value, String> {
    let mut value = serde_json::to_value(model).map_err(|error| error.to_string())?;
    value["vendor"] = Value::String(model.vendor().to_string());
    Ok(value)
}

fn run() -> Result<(), (i32, String)> {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(
        args.next()
            .ok_or((2, "usage: registry_cli <home> [options]".to_string()))?,
    );
    let (provider, active_only, json_output) =
        parse_options(args).map_err(|message| (2, message))?;
    let reg_dir = home.join("registry");
    let providers =
        load_providers(&reg_dir.join("providers.yaml")).map_err(|error| (3, error.to_string()))?;
    let (models, warnings) =
        load_all_models(&reg_dir, &providers).map_err(|error| (3, error.to_string()))?;
    for warning in warnings {
        eprintln!("warning: {warning}");
    }
    let rows: Vec<&ModelEntry> = models
        .iter()
        .filter(|model| provider.as_deref().map_or(true, |id| model.provider == id))
        .filter(|model| !active_only || model.deprecation_status == DeprecationStatus::Active)
        .collect();
    if json_output {
        let json: Vec<Value> = rows
            .iter()
            .map(|model| model_json(model))
            .collect::<Result<_, _>>()
            .map_err(|error| (1, error))?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json).map_err(|error| (1, error.to_string()))?
        );
        return Ok(());
    }
    println!(
        "{:<12} {:<28} {:>10} {:<9} {:<7} {:<7} TOOLS",
        "PROVIDER", "MODEL_ID", "CTX", "PRICE", "LAT", "C/R/W"
    );
    for model in rows {
        let crw = format!(
            "{}/{}/{}",
            model.ability.coding, model.ability.reasoning, model.ability.writing
        );
        let tools = if model.tool_support.is_empty() {
            "-".to_string()
        } else {
            model.tool_support.join(",")
        };
        println!(
            "{:<12} {:<28} {:>10} {:<9} {:<7} {:<7} {}",
            model.provider,
            model.model_id,
            model.context_window,
            serde_json::to_value(model.pricing_tier)
                .map_err(|error| (1, error.to_string()))?
                .as_str()
                .unwrap_or_default(),
            serde_json::to_value(model.latency_tier)
                .map_err(|error| (1, error.to_string()))?
                .as_str()
                .unwrap_or_default(),
            crw,
            tools,
        );
    }
    Ok(())
}

fn main() {
    if let Err((code, message)) = run() {
        eprintln!("{message}");
        std::process::exit(code);
    }
}
