//! Compatibility entry point for `agentrouter dashboard`.
//!
//! Usage: dashboard_cli <home> [port]

use std::collections::HashMap;
use std::path::PathBuf;

fn run() -> Result<(), (i32, String)> {
    let mut args = std::env::args().skip(1);
    let home = PathBuf::from(
        args.next()
            .ok_or((2, "usage: dashboard_cli <home> [port]".to_string()))?,
    );
    let port = args
        .next()
        .map(|value| {
            value
                .parse::<u16>()
                .map_err(|_| (2, "port must be an integer from 0 to 65535".to_string()))
        })
        .transpose()?
        .unwrap_or(8321);
    if args.next().is_some() {
        return Err((2, "usage: dashboard_cli <home> [port]".to_string()));
    }

    let database = home.join("agentrouter.db");
    if !database.is_file() {
        return Err((
            2,
            format!(
                "No decision log found at {}.\nNext: agentrouter init, then agentrouter route \"<task>\"",
                database.display()
            ),
        ));
    }
    let registry = home.join("registry");
    let providers = agentrouter_registry::load_providers(&registry.join("providers.yaml"))
        .map_err(|error| (3, error.to_string()))?;
    let (models, _) = agentrouter_registry::load_all_models(&registry, &providers)
        .map_err(|error| (3, error.to_string()))?;
    let tiers: HashMap<String, String> = models
        .into_iter()
        .map(|model| {
            let tier = serde_json::to_value(model.pricing_tier)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_else(|| "unknown".to_string());
            (model.key(), tier)
        })
        .collect();
    agentrouter_cli::dashboard::serve(&home, port, &tiers)
        .map_err(|error| (1, format!("could not start dashboard: {error}")))
}

fn main() {
    if let Err((code, message)) = run() {
        eprintln!("{message}");
        std::process::exit(code);
    }
}
