use std::collections::HashSet;
use std::io::{self, Read};
use std::path::Path;

use chrono::NaiveDate;
use serde_json::{json, Value};

fn status_value(status: agentrouter_registry::catalog_ops::CatalogStatus) -> Value {
    json!({
        "provider": status.provider,
        "path": status.path.to_string_lossy(),
        "count": status.count,
        "newest": status.newest.map(|date| date.format("%Y-%m-%d").to_string()),
        "age_days": status.age_days,
        "stale": status.stale,
        "source_url": status.source_url,
        "fetched_at": status.fetched_at,
        "tool_version": status.tool_version,
        "summary": status.summary(),
    })
}

fn string_set(value: &Value, name: &str) -> Result<HashSet<String>, String> {
    value[name]
        .as_array()
        .ok_or_else(|| format!("{name} must be an array"))?
        .iter()
        .map(|item| {
            item.as_str()
                .map(str::to_owned)
                .ok_or_else(|| format!("{name} entries must be strings"))
        })
        .collect()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Value = serde_json::from_str(&input)?;
    let result = match request["operation"].as_str() {
        Some("deprecations") => {
            let previous = string_set(&request, "previous")?;
            let current = string_set(&request, "current")?;
            json!({"value": agentrouter_registry::catalog_ops::deprecations(&previous, &current)})
        }
        Some("read_provenance") => {
            let path = request["path"].as_str().ok_or("path must be a string")?;
            json!({"value": agentrouter_registry::catalog_ops::read_provenance(Path::new(path))})
        }
        Some("read_status") => {
            let path = request["path"].as_str().ok_or("path must be a string")?;
            let today = request["today"]
                .as_str()
                .ok_or("today must be an ISO date")?;
            let today = NaiveDate::parse_from_str(today, "%Y-%m-%d")?;
            let status = agentrouter_registry::catalog_ops::read_status(Path::new(path), today)?;
            json!({"value": status_value(status)})
        }
        Some("list_generated") => {
            let reg_dir = request["reg_dir"]
                .as_str()
                .ok_or("reg_dir must be a string")?;
            let today = request["today"]
                .as_str()
                .ok_or("today must be an ISO date")?;
            let today = NaiveDate::parse_from_str(today, "%Y-%m-%d")?;
            let statuses =
                agentrouter_registry::catalog_ops::list_generated(Path::new(reg_dir), today)?;
            json!({"value": statuses.into_iter().map(status_value).collect::<Vec<_>>()})
        }
        Some("rollback") | Some("restore") => {
            let reg_dir = request["reg_dir"]
                .as_str()
                .ok_or("reg_dir must be a string")?;
            let provider = request["provider"]
                .as_str()
                .ok_or("provider must be a string")?;
            let path = if request["operation"] == "rollback" {
                agentrouter_registry::catalog_ops::rollback(Path::new(reg_dir), provider)?
            } else {
                agentrouter_registry::catalog_ops::restore(Path::new(reg_dir), provider)?
            };
            json!({"value": path.map(|path| path.to_string_lossy().into_owned())})
        }
        _ => return Err("unknown operation".into()),
    };
    println!("{}", serde_json::to_string(&result)?);
    Ok(())
}
