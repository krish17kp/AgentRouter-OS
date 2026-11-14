fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!(
        "{}",
        serde_json::to_string(&agentrouter_evaluation::evaluation_api::PUBLIC_EXPORTS)?
    );
    Ok(())
}
