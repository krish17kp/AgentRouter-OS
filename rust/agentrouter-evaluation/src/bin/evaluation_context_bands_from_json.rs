fn main() -> Result<(), Box<dyn std::error::Error>> {
    let report = agentrouter_evaluation::context_bands::evaluate_generalization()
        .map_err(std::io::Error::other)?;
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}
