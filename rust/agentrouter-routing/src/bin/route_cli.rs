//! Takes a routing-gold YAML path and a scenario id, builds the scenario's
//! synthetic registry + classification (defaults mirroring
//! `agentrouter.evaluate.build_classification`/`_CLS_DEFAULTS`), runs
//! `route()`, and prints the `RouteResult` as JSON. Exists purely so
//! `tests/test_routing_rust_compat.py` can diff Rust output against
//! Python's `engine.route()` for the same scenario.

use std::path::PathBuf;

use agentrouter_core::{
    ApprovalLevel, Classification, ContextBand, Level, OutputType, PricingTier, TaskType,
};
use agentrouter_registry::ModelEntry;
use agentrouter_routing::{route, Weights};

fn band(tokens: u32) -> ContextBand {
    if tokens < 8_000 {
        ContextBand::Small
    } else if tokens < 64_000 {
        ContextBand::Medium
    } else {
        ContextBand::Large
    }
}

fn parse_task_type(s: &str) -> TaskType {
    match s {
        "coding" => TaskType::Coding,
        "reasoning" => TaskType::Reasoning,
        "writing" => TaskType::Writing,
        "analysis" => TaskType::Analysis,
        "summarization" => TaskType::Summarization,
        "general" => TaskType::General,
        _ => panic!("unknown task_type {s}"),
    }
}

fn parse_level(s: &str) -> Level {
    match s {
        "low" => Level::Low,
        "medium" => Level::Medium,
        "high" => Level::High,
        _ => panic!("unknown level {s}"),
    }
}

fn parse_output_type(s: &str) -> OutputType {
    match s {
        "code" => OutputType::Code,
        "text" => OutputType::Text,
        "code+tests" => OutputType::CodeTests,
        "data" => OutputType::Data,
        "plan" => OutputType::Plan,
        _ => panic!("unknown output_type {s}"),
    }
}

/// Mirrors `evaluate.build_classification` + `_CLS_DEFAULTS`/`_APPROVAL_BY_RISK`.
fn build_classification(d: &serde_yaml::Mapping) -> Classification {
    let get_str = |key: &str, default: &str| -> String {
        d.get(key)
            .and_then(|v| v.as_str())
            .unwrap_or(default)
            .to_string()
    };
    let task_type = parse_task_type(&get_str("task_type", "coding"));
    let complexity = parse_level(&get_str("complexity", "medium"));
    let risk_str = get_str("risk", "low");
    let risk = parse_level(&risk_str);
    let context_tokens = d
        .get("context_tokens")
        .and_then(|v| v.as_u64())
        .unwrap_or(4000) as u32;
    let output_type = parse_output_type(&get_str("output_type", "code"));
    let tool_needs: Vec<String> = d
        .get("tool_needs")
        .and_then(|v| v.as_sequence())
        .map(|seq| {
            seq.iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();
    let context_band = d
        .get("context_band")
        .and_then(|v| v.as_str())
        .map(|s| match s {
            "small" => ContextBand::Small,
            "medium" => ContextBand::Medium,
            "large" => ContextBand::Large,
            _ => panic!("unknown context_band {s}"),
        })
        .unwrap_or_else(|| band(context_tokens));
    let approval_level = d
        .get("approval_level")
        .and_then(|v| v.as_str())
        .map(|s| match s {
            "auto" => ApprovalLevel::Auto,
            "notify" => ApprovalLevel::Notify,
            "human-approval-required" => ApprovalLevel::HumanApprovalRequired,
            _ => panic!("unknown approval_level {s}"),
        })
        .unwrap_or(match risk {
            Level::Low => ApprovalLevel::Auto,
            Level::Medium => ApprovalLevel::Notify,
            Level::High => ApprovalLevel::HumanApprovalRequired,
        });

    Classification {
        task_type,
        complexity,
        risk,
        context_tokens,
        context_band,
        output_type,
        tool_needs,
        approval_level,
        confidence: 1.0,
        needs_clarification: false,
        alternative_task_type: None,
        ambiguity_reason: None,
    }
}

fn pricing_tier_rank(t: PricingTier) -> u8 {
    match t {
        PricingTier::Free => 0,
        PricingTier::Low => 1,
        PricingTier::Medium => 2,
        PricingTier::High => 3,
        PricingTier::Frontier => 4,
    }
}

fn parse_pricing_tier(s: &str) -> PricingTier {
    match s {
        "free" => PricingTier::Free,
        "low" => PricingTier::Low,
        "medium" => PricingTier::Medium,
        "high" => PricingTier::High,
        "frontier" => PricingTier::Frontier,
        _ => panic!("unknown pricing_tier {s}"),
    }
}

fn main() {
    let mut args = std::env::args().skip(1);
    let gold_path = PathBuf::from(
        args.next()
            .expect("usage: route_cli <gold.yaml> <scenario id>"),
    );
    let scenario_id = args
        .next()
        .expect("usage: route_cli <gold.yaml> <scenario id>");

    let text = std::fs::read_to_string(&gold_path).expect("read gold yaml");
    let doc: serde_yaml::Value = serde_yaml::from_str(&text).expect("parse gold yaml");
    let scenarios = doc
        .get("scenarios")
        .and_then(|v| v.as_sequence())
        .expect("scenarios list");
    let scenario = scenarios
        .iter()
        .find(|s| s.get("id").and_then(|v| v.as_str()) == Some(scenario_id.as_str()))
        .unwrap_or_else(|| panic!("scenario {scenario_id} not found"));

    let models_raw = scenario
        .get("models")
        .and_then(|v| v.as_sequence())
        .expect("models list");
    let mut models: Vec<ModelEntry> = models_raw
        .iter()
        .map(|m| serde_yaml::from_value(m.clone()).expect("model entry"))
        .collect();

    if let Some(cap) = scenario.get("max_pricing_tier").and_then(|v| v.as_str()) {
        let ceiling = pricing_tier_rank(parse_pricing_tier(cap));
        models.retain(|m| pricing_tier_rank(m.pricing_tier) <= ceiling);
    }

    let empty_map = serde_yaml::Mapping::new();
    let cls_map = scenario
        .get("classification")
        .and_then(|v| v.as_mapping())
        .unwrap_or(&empty_map);
    let cls = build_classification(cls_map);

    let result = route(&models, &cls, Weights::default(), None);
    println!("{}", serde_json::to_string(&result).unwrap());
}
