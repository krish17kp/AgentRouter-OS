//! Differential bridge for the historical classifier gold-set report.

use std::io::{self, Read};
use std::path::Path;

use serde_json::{json, Value};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut source = String::new();
    io::stdin().read_to_string(&mut source)?;
    let request: Value = serde_json::from_str(&source)?;
    let operation = request["operation"]
        .as_str()
        .ok_or("operation must be a string")?;
    let report = match operation {
        "load_gold" => {
            let path = request["path"].as_str().ok_or("path must be a string")?;
            match agentrouter_evaluation::legacy_gold::load_gold(Path::new(path)) {
                Ok(cases) => {
                    json!({"ok": true, "error_type": null, "message": null, "cases": cases})
                }
                Err(error) => json!({
                    "ok": false,
                    "error_type": error.python_type(),
                    "message": error.to_string(),
                    "cases": null
                }),
            }
        }
        "grade_cases" => {
            let cases = request["cases"]
                .as_array()
                .ok_or("cases must be an array")?;
            agentrouter_evaluation::legacy_gold::grade_cases(cases)?
        }
        "evaluate_gold" => {
            let path = request["path"].as_str().ok_or("path must be a string")?;
            agentrouter_evaluation::legacy_gold::evaluate(Path::new(path))?
        }
        "write_artifacts" => {
            let report = request.get("report").ok_or("report is required")?;
            let out_dir = request["out_dir"]
                .as_str()
                .ok_or("out_dir must be a string")?;
            let paths =
                agentrouter_evaluation::legacy_gold::write_artifacts(report, Path::new(out_dir))?;
            json!({"paths": paths})
        }
        "grade_routing" => {
            let scenarios = request["scenarios"]
                .as_array()
                .ok_or("scenarios must be an array")?;
            agentrouter_evaluation::legacy_gold::grade_routing(scenarios)?
        }
        "evaluate_routing" => {
            let path = request["path"].as_str().ok_or("path must be a string")?;
            agentrouter_evaluation::legacy_gold::evaluate_routing(Path::new(path))?
        }
        _ => return Err(format!("unknown operation '{operation}'").into()),
    };
    println!("{}", serde_json::to_string(&json!({"value": report}))?);
    Ok(())
}
