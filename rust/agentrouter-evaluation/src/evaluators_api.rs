//! Public evaluator package facade, mirrored from
//! `agentrouter.evaluation.evaluators`.

pub use crate::{
    evaluate_feedback, evaluate_performance, evaluate_platform, evaluate_provider,
    evaluate_routing, evaluate_safety,
};

use std::path::Path;
use std::process::Command;

use agentrouter_registry::{load_models, load_providers, ModelEntry};
use serde::Deserialize;

pub const PUBLIC_EXPORTS: [&str; 7] = [
    "load_seed_models",
    "evaluate_routing",
    "evaluate_safety",
    "evaluate_platform",
    "evaluate_provider",
    "evaluate_feedback",
    "evaluate_performance",
];

/// The real command and group surface shipped by the Rust CLI. Keeping this
/// declaration in the evaluator package makes default platform grading and the
/// CLI's internal surface probe consume the same contract.
pub const RUST_CLI_COMMANDS: [&str; 12] = [
    "dashboard",
    "doctor",
    "evaluate",
    "execute",
    "explain",
    "feedback",
    "init",
    "mcp",
    "route",
    "server",
    "setup",
    "stats",
];

pub const RUST_CLI_GROUPS: [&str; 8] = [
    "dataset",
    "eval",
    "hosts",
    "models",
    "plugin",
    "prompt",
    "providers",
    "registry",
];

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct CliSurface {
    commands: Vec<String>,
    groups: Vec<String>,
}

/// Query the installed AgentRouter CLI instead of grading a caller-provided or
/// evaluator-local manifest. Resolving it from `PATH` keeps this public library
/// independent of the executable that happens to embed it. Missing, failing,
/// or malformed runtime discovery is an error, never a fabricated score.
pub fn runtime_cli_surface() -> Result<(Vec<String>, Vec<String>), String> {
    let output = Command::new("agentrouter")
        .arg("__evaluation_surface")
        .output()
        .map_err(|error| format!("could not query the installed Rust CLI surface: {error}"))?;
    if !output.status.success() {
        return Err("the installed Rust CLI could not report its command surface".to_owned());
    }
    let surface: CliSurface = serde_json::from_slice(&output.stdout)
        .map_err(|error| format!("the sibling Rust CLI returned an invalid surface: {error}"))?;
    Ok((surface.commands, surface.groups))
}

/// Parse the packaged offline seed catalog using the same validated registry
/// loaders as the runtime. The temporary directory is private and contains
/// only compile-time embedded, read-only source data.
pub fn load_seed_models() -> Result<Vec<ModelEntry>, String> {
    let directory = tempfile::tempdir().map_err(|error| error.to_string())?;
    let providers_path = directory.path().join("providers.yaml");
    let models_path = directory.path().join("models.yaml");
    std::fs::write(
        &providers_path,
        include_str!("../../../agentrouter/seeds/providers.yaml"),
    )
    .map_err(|error| error.to_string())?;
    std::fs::write(
        &models_path,
        include_str!("../../../agentrouter/seeds/models.yaml"),
    )
    .map_err(|error| error.to_string())?;
    let providers =
        load_providers(Path::new(&providers_path)).map_err(|error| error.to_string())?;
    let (models, _warnings) =
        load_models(Path::new(&models_path), &providers).map_err(|error| error.to_string())?;
    Ok(models)
}
