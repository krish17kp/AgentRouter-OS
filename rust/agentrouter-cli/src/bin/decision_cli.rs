//! Compatibility probe for the Rust `explain --json` and
//! `prompt generate --from` paths against a real Python-created decision log.
//!
//! Usage: decision_cli <home> <explain|prompt> <decision_id> [tool]

use serde_json::Value;
use std::path::PathBuf;

fn value_text(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(text)) => text.clone(),
        Some(Value::Number(number)) => number.to_string(),
        Some(Value::Bool(flag)) => flag.to_string(),
        Some(Value::Null) | None => "-".to_owned(),
        Some(other) => other.to_string(),
    }
}

fn score_text(value: Option<&Value>) -> String {
    value
        .and_then(Value::as_f64)
        .map(|number| format!("{number:.3}"))
        .unwrap_or_else(|| value_text(value))
}

fn explain_text(payload: &Value) -> Result<String, String> {
    let classification = payload
        .get("classification")
        .and_then(Value::as_object)
        .ok_or_else(|| "stored decision has invalid classification".to_owned())?;
    let tools = classification
        .get("tool_needs")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .collect::<Vec<_>>()
                .join(",")
        })
        .unwrap_or_default();
    let task = value_text(payload.get("task"));
    let mut output = format!(
        "Task: \"{task}\"\nClassification: {}/{}/{}/{} | tools[{tools}]\n",
        value_text(classification.get("task_type")),
        value_text(classification.get("complexity")),
        value_text(classification.get("risk")),
        value_text(classification.get("context_band")),
    );
    let scores = payload
        .get("scores")
        .and_then(Value::as_array)
        .ok_or_else(|| "stored decision has invalid scores".to_owned())?;
    let excluded = payload
        .get("excluded")
        .and_then(Value::as_array)
        .ok_or_else(|| "stored decision has invalid exclusions".to_owned())?;
    output.push_str(&format!(
        "\nEligibility: {} models -> {} eligible\n",
        scores.len() + excluded.len(),
        scores.len()
    ));
    for item in excluded {
        output.push_str(&format!(
            "  excluded {}: {}\n",
            value_text(item.get("model")),
            value_text(item.get("reason"))
        ));
    }
    output.push_str("\nScores\n");
    output.push_str(&format!(
        "  {:<42} {:>5} {:>5} {:>5} {:>5} {:>5}  score\n",
        "model", "cap", "cost", "lat", "ctx", "adj"
    ));
    let fallback_model = payload
        .get("fallback")
        .and_then(|value| value.get("model"))
        .and_then(Value::as_str);
    for (index, item) in scores.iter().enumerate() {
        let terms = item
            .get("terms")
            .and_then(Value::as_object)
            .ok_or_else(|| "stored decision has invalid score terms".to_owned())?;
        let model = value_text(item.get("model"));
        let marker = if index == 0 {
            "  <- recommended"
        } else if fallback_model == Some(model.as_str()) {
            "  <- fallback"
        } else {
            ""
        };
        output.push_str(&format!(
            "  {:<42} {:>5} {:>5} {:>5} {:>5} {:>5}  {:>5}{}\n",
            model,
            value_text(terms.get("cap")),
            value_text(terms.get("cost")),
            value_text(terms.get("lat")),
            value_text(terms.get("ctx")),
            value_text(terms.get("adj")),
            score_text(item.get("score")),
            marker
        ));
    }
    let weights = payload
        .get("weights")
        .and_then(Value::as_object)
        .ok_or_else(|| "stored decision has invalid weights".to_owned())?;
    output.push_str(&format!(
        "\nWeights: cap {} cost {} lat {} ctx {}\n",
        value_text(weights.get("w_cap")),
        value_text(weights.get("w_cost")),
        value_text(weights.get("w_lat")),
        value_text(weights.get("w_ctx")),
    ));
    if let Some(shifts) = payload.get("weight_shifts").and_then(Value::as_array) {
        for shift in shifts {
            output.push_str(&format!("  shift: {}\n", value_text(Some(shift))));
        }
    }
    let gates = payload
        .get("gates")
        .and_then(Value::as_object)
        .ok_or_else(|| "stored decision has invalid gates".to_owned())?;
    let auto_execute = gates
        .get("auto_execute_allowed")
        .and_then(Value::as_bool)
        .map(|allowed| if allowed { "True" } else { "False" })
        .unwrap_or("-");
    output.push_str(&format!(
        "Gate: approval={}, auto_execute_allowed={}\n",
        value_text(gates.get("approval_level")),
        auto_execute,
    ));
    Ok(output)
}

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(
        args.next()
            .ok_or("usage: decision_cli <home> <op> <id> [tool]")?,
    );
    let op = args.next().ok_or("operation is required")?;
    let id = args.next().ok_or("decision id is required")?;
    let mut json_output = false;
    let mut text_output = false;
    let mut tool = None;
    while let Some(argument) = args.next() {
        match argument.as_str() {
            "--json" => json_output = true,
            "--text" => text_output = true,
            "--tool" => {
                tool = Some(args.next().ok_or("--tool needs a value")?);
            }
            value if op == "prompt" && tool.is_none() => tool = Some(value.to_owned()),
            option => return Err(format!("unknown option '{option}'")),
        }
    }
    let conn = agentrouter_storage::connect(&home).map_err(|e| e.to_string())?;
    let payload = agentrouter_storage::load_decision(&conn, &id)
        .map_err(|e| e.to_string())?
        .ok_or_else(|| format!("No decision found with id '{id}'."))?;
    match op.as_str() {
        "explain" if text_output && !json_output => print!("{}", explain_text(&payload)?),
        "explain" => println!(
            "{}",
            serde_json::to_string(&payload).map_err(|e| e.to_string())?
        ),
        "prompt" => {
            let prompt = agentrouter_cli::prompt_from_decision(&payload, tool.as_deref())?;
            print!("{prompt}");
        }
        _ => return Err(format!("unknown operation '{op}'")),
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
