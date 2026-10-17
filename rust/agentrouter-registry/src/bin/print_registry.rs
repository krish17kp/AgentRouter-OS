//! Emits a stable registry summary for the Python/Rust compatibility test.
use agentrouter_registry::{parse_models, parse_providers};
use serde_json::json;

fn main() {
    let providers =
        parse_providers(include_str!("../../../../agentrouter/seeds/providers.yaml"))
            .expect("seed providers must parse");
    let (models, warnings) = parse_models(
        include_str!("../../../../agentrouter/seeds/models.yaml"),
        &providers,
    )
    .expect("seed models must parse");
    let items: Vec<_> = models
        .iter()
        .map(|model| {
            json!({
                "key": model.key(),
                "vendor_key": model.vendor_key(),
                "name": model.name(),
                "context_window": model.context_window,
                "max_output_tokens": model.max_output_tokens,
                "pricing_tier": model.pricing_tier,
                "tool_support": model.tool_support,
                "fallback": model.fallback,
            })
        })
        .collect();
    println!(
        "{}",
        json!({
            "providers": providers.keys().collect::<Vec<_>>(),
            "models": items,
            "warnings": warnings,
        })
    );
}
