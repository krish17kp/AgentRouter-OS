use agentrouter_evaluation::evaluators_api::{load_seed_models, PUBLIC_EXPORTS};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let models = load_seed_models().map_err(std::io::Error::other)?;
    let mut serialized_models = Vec::with_capacity(models.len());
    for model in &models {
        let mut value = serde_json::to_value(model)?;
        // Python's ModelEntry validator materializes this dependent default;
        // Rust keeps the source value optional internally and exposes the
        // effective value through `vendor()`.
        value["vendor"] = serde_json::json!(model.vendor());
        serialized_models.push(value);
    }
    println!(
        "{}",
        serde_json::to_string(&serde_json::json!({
            "exports": PUBLIC_EXPORTS,
            "models": serialized_models,
        }))?
    );
    Ok(())
}
