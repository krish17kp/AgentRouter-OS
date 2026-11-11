//! Offline fixture probe for Python/Rust feedback-storage evaluation parity.

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!(
        "{}",
        serde_json::to_string(&agentrouter_evaluation::evaluate_feedback()?)?
    );
    Ok(())
}
