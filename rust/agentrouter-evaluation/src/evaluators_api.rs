//! Public evaluator package facade, mirrored from
//! `agentrouter.evaluation.evaluators`.

pub use crate::{
    evaluate_feedback, evaluate_performance as evaluate_performance_with_models,
    evaluate_performance_with, evaluate_platform as evaluate_platform_with_surface,
    evaluate_provider as evaluate_provider_with_models, evaluate_routing, evaluate_routing_with,
    evaluate_safety, evaluate_safety_with,
};

use std::path::Path;
use std::process::Command;
use std::sync::OnceLock;

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
/// evaluator-local manifest. Production resolves `agentrouter` from `PATH`;
/// `AGENTROUTER_EVALUATION_CLI` provides an explicit executable path for
/// hermetic embedding and process-failure tests. Missing, failing, or malformed
/// runtime discovery is an error, never a fabricated score.
pub fn runtime_cli_surface() -> Result<(Vec<String>, Vec<String>), String> {
    let executable =
        std::env::var_os("AGENTROUTER_EVALUATION_CLI").unwrap_or_else(|| "agentrouter".into());
    let output = Command::new(executable)
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
static SEED_MODELS: OnceLock<Vec<ModelEntry>> = OnceLock::new();

pub fn load_seed_models() -> Result<Vec<ModelEntry>, String> {
    load_cached_seed_models(&SEED_MODELS, load_seed_models_uncached)
}

fn load_cached_seed_models<F>(
    cache: &OnceLock<Vec<ModelEntry>>,
    loader: F,
) -> Result<Vec<ModelEntry>, String>
where
    F: FnOnce() -> Result<Vec<ModelEntry>, String>,
{
    if let Some(models) = cache.get() {
        return Ok(models.clone());
    }
    let models = loader()?;
    let _ = cache.set(models.clone());
    Ok(cache.get().cloned().unwrap_or(models))
}

fn load_seed_models_uncached() -> Result<Vec<ModelEntry>, String> {
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

/// Python facade-compatible no-argument provider evaluator.
pub fn evaluate_provider() -> Result<serde_json::Value, String> {
    crate::evaluate_provider_default()
}

/// Python facade-compatible no-argument performance evaluator.
pub fn evaluate_performance() -> Result<serde_json::Value, String> {
    crate::evaluate_default_performance()
}

/// Python facade-compatible no-argument platform evaluator using the installed
/// Rust CLI contract.
pub fn evaluate_platform() -> Result<serde_json::Value, String> {
    let (commands, groups) = runtime_cli_surface()?;
    Ok(crate::evaluate_platform(&commands, &groups))
}

#[cfg(test)]
mod tests {
    #[test]
    fn packaged_seed_loader_reuses_one_validated_catalog() {
        let first = super::load_seed_models().expect("packaged seeds");
        let cached = super::SEED_MODELS.get().expect("seed cache initialized");
        let second = super::load_seed_models().expect("cached packaged seeds");
        assert_eq!(
            serde_json::to_value(first).expect("first seed catalog JSON"),
            serde_json::to_value(second).expect("cached seed catalog JSON")
        );
        assert!(!cached.is_empty());
    }

    #[test]
    fn failed_seed_load_is_retried_instead_of_cached() {
        let cache = std::sync::OnceLock::new();
        let failed = super::load_cached_seed_models(&cache, || Err("transient".to_owned()));
        assert_eq!(failed.unwrap_err(), "transient");
        assert!(cache.get().is_none());

        let expected = super::load_seed_models_uncached().expect("packaged seeds");
        let recovered = super::load_cached_seed_models(&cache, || Ok(expected.clone()))
            .expect("retry succeeds");
        assert_eq!(
            serde_json::to_value(recovered).expect("recovered JSON"),
            serde_json::to_value(expected).expect("expected JSON")
        );
    }

    #[test]
    fn facade_preserves_explicit_and_injected_evaluator_entrypoints() {
        let models = super::load_seed_models().expect("packaged seeds");
        let empty_cases = Vec::<crate::EvaluationCase>::new();
        let no_prediction = &|_: &str| -> agentrouter_core::Classification {
            panic!("empty inputs must not classify")
        };

        assert_eq!(super::evaluate_provider_with_models(&models)["score"], 1.0);
        assert_eq!(
            super::evaluate_platform_with_surface(&[], &[])["detail"]["present"],
            0
        );
        assert_eq!(
            super::evaluate_performance_with_models(&models, &[])["detail"]["n_samples"],
            0
        );
        assert_eq!(
            super::evaluate_performance_with(&models, &[], no_prediction)["detail"]["n_samples"],
            0
        );
        assert_eq!(
            super::evaluate_routing_with(&empty_cases, &models, no_prediction)["score"],
            0.0
        );
        assert_eq!(
            super::evaluate_safety_with(&empty_cases, no_prediction)["score"],
            1.0
        );
    }
}
