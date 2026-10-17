//! Takes a routing-gold YAML path, a scenario id, and a JSON-encoded
//! `RouteControls`, applies `apply_controls` to that scenario's model list,
//! and prints `{"kept": [keys...], "dropped": [{"model","reason"}...]}`.
//! Exists purely so `tests/test_controls_rust_compat.py` can diff Rust
//! output against Python's `controls.apply_controls()` for the same input.

use std::path::PathBuf;

use agentrouter_policy::controls::{apply_controls, RouteControls};
use agentrouter_registry::ModelEntry;
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize, Default)]
struct ControlsInput {
    #[serde(default)]
    vendor: Vec<String>,
    #[serde(default)]
    exclude_vendor: Vec<String>,
    #[serde(default)]
    model: Option<String>,
    #[serde(default)]
    host: Vec<String>,
    #[serde(default)]
    exclude_host: Vec<String>,
    #[serde(default)]
    max_price: Option<f64>,
    #[serde(default)]
    stable_only: bool,
    #[serde(default)]
    available_only: bool,
    #[serde(default)]
    prohibit_tool: Vec<String>,
}

fn main() {
    let mut args = std::env::args().skip(1);
    let gold_path = PathBuf::from(
        args.next()
            .expect("usage: controls_cli <gold.yaml> <scenario id> <controls json>"),
    );
    let scenario_id = args
        .next()
        .expect("usage: controls_cli <gold.yaml> <scenario id> <controls json>");
    let controls_json = args
        .next()
        .expect("usage: controls_cli <gold.yaml> <scenario id> <controls json>");

    let text = std::fs::read_to_string(&gold_path).expect("read gold yaml");
    let doc: serde_yaml::Value = serde_yaml::from_str(&text).expect("parse gold yaml");
    let scenarios = doc
        .get("scenarios")
        .and_then(|v| v.as_sequence())
        .expect("scenarios list");
    let scenario = scenarios
        .iter()
        .find(|s| s.get("id").and_then(|v| v.as_str()) == Some(scenario_id.as_str()))
        .unwrap_or_else(|| panic!("scenario {scenario_id} not found"));

    let models_raw = scenario
        .get("models")
        .and_then(|v| v.as_sequence())
        .expect("models list");
    let models: Vec<ModelEntry> = models_raw
        .iter()
        .map(|m| serde_yaml::from_value(m.clone()).expect("model entry"))
        .collect();

    let input: ControlsInput = serde_json::from_str(&controls_json).expect("controls json");
    let controls = RouteControls {
        vendor: input.vendor,
        exclude_vendor: input.exclude_vendor,
        model: input.model,
        host: input.host,
        exclude_host: input.exclude_host,
        max_price: input.max_price,
        stable_only: input.stable_only,
        available_only: input.available_only,
        prohibit_tool: input.prohibit_tool,
    };

    let (kept, dropped) = apply_controls(&models, &controls);
    let out = json!({
        "kept": kept.iter().map(|m| m.key()).collect::<Vec<_>>(),
        "dropped": dropped.iter().map(|d| json!({"model": d.model, "reason": d.reason})).collect::<Vec<_>>(),
    });
    println!("{}", serde_json::to_string(&out).unwrap());
}
