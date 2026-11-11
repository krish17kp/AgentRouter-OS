//! Offline differential probe for LongBench v2 row normalization.

use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    rows: Vec<agentrouter_evaluation::LongBenchRawRow>,
    #[serde(default)]
    bucket_tokens: Vec<i64>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;
    let input: Input = serde_json::from_str(&input)?;
    let cases = agentrouter_evaluation::normalize_longbench_rows(&input.rows);
    let buckets: Vec<_> = input
        .bucket_tokens
        .iter()
        .map(|tokens| agentrouter_evaluation::longbench_bucket_for(*tokens))
        .collect();
    println!(
        "{}",
        serde_json::to_string(&serde_json::json!({"cases": cases, "buckets": buckets}))?
    );
    Ok(())
}
