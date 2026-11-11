//! Reproducible local benchmark for the pure Rust filtering and ranking pass.
//!
//! Usage: routing_bench [--iterations N] [--fleets N ...]

use std::time::Instant;

use agentrouter_core::{ApprovalLevel, Classification, ContextBand, Level, OutputType, TaskType};
use agentrouter_registry::ModelEntry;
use agentrouter_routing::{route, Weights};
use serde_json::json;

fn model(index: usize) -> ModelEntry {
    let tier = ["free", "low", "medium", "high", "frontier"][index % 5];
    let latency = ["fast", "medium", "slow"][index % 3];
    let context = [16_000, 64_000, 256_000][index % 3];
    let coding = index * 7 % 11;
    let reasoning = index * 5 % 11;
    let writing = index * 3 % 11;
    let tools = if !index.is_multiple_of(5) {
        "[file-edit]"
    } else {
        "[]"
    };
    let vision = index.is_multiple_of(7);
    let yaml = format!(
        "provider: provider-{}\nmodel_id: synthetic-model-{index:05}\ncontext_window: {context}\nmax_output_tokens: 8000\npricing_tier: {tier}\nlatency_tier: {latency}\nability: {{coding: {coding}, reasoning: {reasoning}, writing: {writing}}}\ntool_support: {tools}\nvision_support: {vision}\ndeprecation_status: active\n",
        index % 8,
    );
    serde_yaml::from_str(&yaml).expect("benchmark model fixture is valid")
}

fn classification() -> Classification {
    Classification {
        task_type: TaskType::Coding,
        complexity: Level::Medium,
        risk: Level::Low,
        context_tokens: 12_000,
        context_band: ContextBand::Small,
        output_type: OutputType::Code,
        tool_needs: vec!["file-edit".to_owned()],
        approval_level: ApprovalLevel::Auto,
        confidence: 1.0,
        needs_clarification: false,
        alternative_task_type: None,
        ambiguity_reason: None,
    }
}

fn measure(size: usize, iterations: usize) -> serde_json::Value {
    let models = (0..size).map(model).collect::<Vec<_>>();
    let class = classification();
    for _ in 0..iterations.min(100) {
        std::hint::black_box(route(&models, &class, Weights::default(), None));
    }
    let mut samples_ns = Vec::with_capacity(iterations);
    let started = Instant::now();
    for _ in 0..iterations {
        let sample_started = Instant::now();
        std::hint::black_box(route(&models, &class, Weights::default(), None));
        samples_ns.push(sample_started.elapsed().as_nanos());
    }
    let elapsed = started.elapsed().as_secs_f64();
    samples_ns.sort_unstable();
    let middle = samples_ns.len() / 2;
    let p50_ns = if samples_ns.len() % 2 == 0 {
        (samples_ns[middle - 1] + samples_ns[middle]) as f64 / 2.0
    } else {
        samples_ns[middle] as f64
    };
    let p95_index = (samples_ns.len() * 95 / 100).min(samples_ns.len() - 1);
    json!({
        "candidate_models": size,
        "iterations": iterations,
        "p50_us": (p50_ns / 1_000.0 * 100.0).round() / 100.0,
        "p95_us": (samples_ns[p95_index] as f64 / 1_000.0 * 100.0).round() / 100.0,
        "routes_per_second": (iterations as f64 / elapsed * 100.0).round() / 100.0,
    })
}

fn main() {
    let mut args = std::env::args().skip(1);
    let mut iterations = 2_000usize;
    let mut fleets = vec![10usize, 100, 1_000];
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--iterations" => {
                iterations = args
                    .next()
                    .and_then(|value| value.parse().ok())
                    .unwrap_or(0);
            }
            "--fleets" => {
                fleets.clear();
                for value in args {
                    let Some(size) = value.parse::<usize>().ok() else {
                        eprintln!("fleet sizes must be positive integers");
                        std::process::exit(2);
                    };
                    fleets.push(size);
                }
                break;
            }
            _ => {
                eprintln!("usage: routing_bench [--iterations N] [--fleets N ...]");
                std::process::exit(2);
            }
        }
    }
    if iterations == 0 || fleets.is_empty() || fleets.contains(&0) {
        eprintln!("iterations and fleet sizes must be positive");
        std::process::exit(2);
    }
    let results = fleets
        .into_iter()
        .map(|size| measure(size, iterations))
        .collect::<Vec<_>>();
    println!(
        "{}",
        json!({
            "benchmark": "rust-pure-routing-v1",
            "warmup_iterations": iterations.min(100),
            "results": results,
        })
    );
}
