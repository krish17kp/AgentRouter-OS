fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!(
        "{}",
        serde_json::to_string(&serde_json::json!({
            "evaluation.adapters": agentrouter_evaluation::package_markers::ADAPTERS_PUBLIC_EXPORTS,
            "server": agentrouter_evaluation::package_markers::SERVER_PUBLIC_EXPORTS,
        }))?
    );
    Ok(())
}
