//! Drives `agentrouter-storage` against a given home dir from a small set
//! of subcommands, printing JSON. Exists purely so
//! `tests/test_store_rust_compat.py` can diff Rust output against Python's
//! `agentrouter.store` for the same SQLite database and operations.
//!
//! Usage: store_cli <home_dir> <op> [args...]
//!   save <task> <payload_json>          -> decision id string
//!   recent-ids <n>                      -> JSON array
//!   recent-decisions <n>                -> JSON array
//!   aggregate-stats                     -> JSON object
//!   load <decision_id>                  -> JSON object or null
//!   feedback <decision_id> <rating> <note> -> JSON bool
//!   snapshot <destination>              -> JSON bool

use std::path::PathBuf;

use agentrouter_storage::*;

fn main() {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(args.next().expect("usage: store_cli <home> <op> [args...]"));
    let op = args.next().expect("usage: store_cli <home> <op> [args...]");
    let conn = connect(&home).expect("connect");

    match op.as_str() {
        "save" => {
            let task = args.next().expect("task");
            let payload_json = args.next().expect("payload json");
            let payload: serde_json::Value = serde_json::from_str(&payload_json).unwrap();
            let id = save_decision(&conn, &task, &payload).unwrap();
            println!("{}", serde_json::to_string(&id).unwrap());
        }
        "recent-ids" => {
            let n: i64 = args.next().expect("n").parse().unwrap();
            let ids = recent_ids(&conn, n).unwrap();
            println!("{}", serde_json::to_string(&ids).unwrap());
        }
        "recent-decisions" => {
            let n: i64 = args.next().expect("n").parse().unwrap();
            let d = recent_decisions(&conn, n).unwrap();
            println!("{}", serde_json::to_string(&d).unwrap());
        }
        "aggregate-stats" => {
            let tier_by_key = args.next().map(|raw| {
                serde_json::from_str::<std::collections::HashMap<String, String>>(&raw).unwrap()
            });
            let stats = aggregate_stats(&conn, tier_by_key.as_ref()).unwrap();
            println!("{}", serde_json::to_string(&stats).unwrap());
        }
        "load" => {
            let id = args.next().expect("decision id");
            let d = load_decision(&conn, &id).unwrap();
            println!("{}", serde_json::to_string(&d).unwrap());
        }
        "feedback" => {
            let id = args.next().expect("decision id");
            let rating: i64 = args
                .next()
                .expect("rating")
                .parse()
                .expect("integer rating");
            let note = args.next().unwrap_or_default();
            let recorded = record_feedback(&conn, &id, rating, &note).unwrap();
            println!("{}", serde_json::to_string(&recorded).unwrap());
        }
        "snapshot" => {
            let destination = PathBuf::from(args.next().expect("destination"));
            snapshot(&home, &destination).unwrap();
            println!("true");
        }
        other => panic!("unknown op {other}"),
    }
}
