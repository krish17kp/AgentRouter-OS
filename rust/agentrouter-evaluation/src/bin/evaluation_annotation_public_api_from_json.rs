fn main() -> Result<(), Box<dyn std::error::Error>> {
    let api = serde_json::json!({
        "SCHEMA_VERSION": agentrouter_evaluation::annotation_api::SCHEMA_VERSION,
        "CATEGORIES": agentrouter_evaluation::annotation_api::CATEGORIES,
        "SPLITS": agentrouter_evaluation::annotation_api::SPLITS,
    });
    println!("{}", serde_json::to_string(&api)?);
    Ok(())
}
