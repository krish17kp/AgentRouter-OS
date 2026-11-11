//! Public evaluator package facade, mirrored from
//! `agentrouter.evaluation.evaluators`.

pub use crate::{
    evaluate_feedback, evaluate_performance, evaluate_platform, evaluate_provider,
    evaluate_routing, evaluate_safety,
};

use std::path::Path;

use agentrouter_registry::{load_models, load_providers, ModelEntry};

pub const PUBLIC_EXPORTS: [&str; 7] = [
    "load_seed_models",
    "evaluate_routing",
    "evaluate_safety",
    "evaluate_platform",
    "evaluate_provider",
    "evaluate_feedback",
    "evaluate_performance",
];

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
