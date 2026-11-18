//! Deterministic environment snapshot probe for Python/Rust parity.

use std::io::{self, Read};

use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    agentrouter_version: String,
    python: String,
    platform: String,
    git_sha: Option<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let request: Request = serde_json::from_str(&input)?;
    println!(
        "{}",
        agentrouter_evaluation::environment_snapshot(
            &request.agentrouter_version,
            &request.python,
            &request.platform,
            request.git_sha.as_deref(),
        )
    );
    Ok(())
}
