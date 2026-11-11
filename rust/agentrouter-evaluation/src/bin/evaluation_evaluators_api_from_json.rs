use agentrouter_evaluation::evaluators_api::{load_seed_models, PUBLIC_EXPORTS};
use serde::Serialize;

#[derive(Serialize)]
struct ModelSummary<'a> {
    provider: &'a str,
    vendor: &'a str,
    model_id: &'a str,
    name: &'a str,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let models = load_seed_models().map_err(std::io::Error::other)?;
    let summaries = models
        .iter()
        .map(|model| ModelSummary {
            provider: &model.provider,
            vendor: model.vendor(),
            model_id: &model.model_id,
            name: model.name(),
        })
        .collect::<Vec<_>>();
    println!(
        "{}",
        serde_json::to_string(&serde_json::json!({
            "exports": PUBLIC_EXPORTS,
            "models": summaries,
        }))?
    );
    Ok(())
}
