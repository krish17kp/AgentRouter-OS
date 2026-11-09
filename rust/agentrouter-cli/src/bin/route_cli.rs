//! Drives the ported `route --json` pipeline against a real
//! `AGENTROUTER_HOME` (registries + optional config.yaml + decision log),
//! printing the same payload shape `agentrouter route --json` prints
//! (without the `decision_id`/`task` wrapper keys added by the caller, see
//! `agentrouter_cli::route_payload`). Exists purely so
//! `tests/test_cli_route_rust_compat.py` can diff Rust output against
//! Python's `agentrouter route` CLI for the same registries and task.
//!
//! Usage: route_cli <home> <task> [prefer] [--save]
//! `--save` persists the Rust decision into the existing SQLite log and emits
//! the Python CLI's `{decision_id, task, ...payload}` JSON envelope.

use std::path::PathBuf;

use agentrouter_classifier::{classify, ClassifyOptions};
use agentrouter_registry::{load_all_models, load_providers};
use agentrouter_routing::Weights;

fn main() {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(
        args.next()
            .expect("usage: route_cli <home> <task> [prefer]"),
    );
    let task = args
        .next()
        .expect("usage: route_cli <home> <task> [prefer]");
    let remaining: Vec<String> = args.collect();
    let save = remaining.iter().any(|arg| arg == "--save");
    let prefer = remaining.iter().find(|arg| arg.as_str() != "--save");

    let reg_dir = home.join("registry");
    let providers = load_providers(&reg_dir.join("providers.yaml")).expect("load providers");
    let (models, _warnings) = load_all_models(&reg_dir, &providers).expect("load models");

    let cls = classify(&task, &ClassifyOptions::default());

    let conn = agentrouter_storage::connect(&home).expect("connect store");
    let (weights, note) =
        agentrouter_cli::learned_weights(&conn, &Weights::default()).expect("learned weights");

    let mut payload = agentrouter_cli::route_payload(
        &task,
        &models,
        &cls,
        weights,
        prefer.map(String::as_str),
        note,
    );
    if save {
        let decision_id = agentrouter_storage::save_decision(&conn, &task, &payload)
            .expect("save decision to existing SQLite log");
        payload["decision_id"] = serde_json::json!(decision_id);
        payload["task"] = serde_json::json!(task);
    }
    println!("{}", serde_json::to_string(&payload).unwrap());
}
