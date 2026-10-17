//! Drives the ported `route --json` pipeline against a real
//! `AGENTROUTER_HOME` (registries + optional config.yaml + decision log),
//! printing the same payload shape `agentrouter route --json` prints
//! (without the `decision_id`/`task` wrapper keys added by the caller, see
//! `agentrouter_cli::route_payload`). Exists purely so
//! `tests/test_cli_route_rust_compat.py` can diff Rust output against
//! Python's `agentrouter route` CLI for the same registries and task.
//!
//! Usage: route_cli <home> <task> [prefer]

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
    let prefer = args.next();

    let reg_dir = home.join("registry");
    let providers = load_providers(&reg_dir.join("providers.yaml")).expect("load providers");
    let (models, _warnings) = load_all_models(&reg_dir, &providers).expect("load models");

    let cls = classify(&task, &ClassifyOptions::default());

    let conn = agentrouter_storage::connect(&home).expect("connect store");
    let (weights, note) =
        agentrouter_cli::learned_weights(&conn, &Weights::default()).expect("learned weights");

    let payload =
        agentrouter_cli::route_payload(&task, &models, &cls, weights, prefer.as_deref(), note);
    println!("{}", serde_json::to_string(&payload).unwrap());
}
