//! Offline probe for the Rust OpenAPI trusted-baseline loader.

use std::path::PathBuf;

fn main() {
    let Some(path) = std::env::args_os().nth(1).map(PathBuf::from) else {
        eprintln!("usage: contract_baseline_from_file <openapi.json>");
        std::process::exit(2);
    };
    match agentrouter_cli::contract::load_baseline_file(&path) {
        Ok(document) => match serde_json::to_string(&document) {
            Ok(text) => println!("{text}"),
            Err(error) => {
                eprintln!("serialization: {error}");
                std::process::exit(2);
            }
        },
        Err(error) => {
            eprintln!("{}: {error}", error.kind.as_str());
            std::process::exit(2);
        }
    }
}
