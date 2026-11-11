use agentrouter_cli::harness::detect_harness;

fn main() {
    println!(
        "{}",
        serde_json::to_string(&detect_harness()).expect("serialize harness")
    );
}
