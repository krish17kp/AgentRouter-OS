//! Offline provider catalog conversion from `agentrouter/refresh.py`.
//!
//! Network access and generated-file writes remain outside this crate. These
//! functions convert provider payloads and perform the same filtering,
//! validation, and warning behavior without requiring credentials or network.

use chrono::{Local, NaiveDate};
use serde_json::Value;
use thiserror::Error;

use crate::{
    Ability, AbilitySource, DeprecationStatus, LatencyTier, ModelEntry, ReleaseChannel,
    SnapshotType,
};
use agentrouter_core::PricingTier;

const OPENROUTER_ABILITY: [(f64, PricingTier); 4] = [
    (0.0, PricingTier::Free),
    (1e-6, PricingTier::Low),
    (5e-6, PricingTier::Medium),
    (1.5e-5, PricingTier::High),
];

#[derive(Debug, Error, PartialEq, Eq)]
#[error("{0}")]
pub struct RefreshError(pub String);

#[derive(Clone, Copy)]
struct Family {
    prefix: &'static str,
    context: u32,
    max_output: u32,
    tier: PricingTier,
    ability: (u8, u8, u8),
    tools: bool,
    vision: bool,
}

struct EntryData<'a> {
    provider: &'a str,
    model_id: &'a str,
    display_name: Option<String>,
    context_window: serde_json::Number,
    max_output_tokens: serde_json::Number,
    pricing_tier: PricingTier,
    ability_scores: (u8, u8, u8),
    tool_support: Vec<String>,
    vision_support: bool,
    notes: &'a str,
}

const OPENAI_FAMILIES: &[Family] = &[
    Family {
        prefix: "gpt-4o-mini",
        context: 128_000,
        max_output: 16_384,
        tier: PricingTier::Low,
        ability: (7, 6, 7),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "gpt-4o",
        context: 128_000,
        max_output: 16_384,
        tier: PricingTier::Medium,
        ability: (8, 7, 8),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "gpt-4.1-nano",
        context: 1_000_000,
        max_output: 32_768,
        tier: PricingTier::Low,
        ability: (7, 6, 7),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "gpt-4.1-mini",
        context: 1_000_000,
        max_output: 32_768,
        tier: PricingTier::Low,
        ability: (8, 7, 7),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "gpt-4.1",
        context: 1_000_000,
        max_output: 32_768,
        tier: PricingTier::Medium,
        ability: (8, 8, 8),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "gpt-5-mini",
        context: 400_000,
        max_output: 128_000,
        tier: PricingTier::Low,
        ability: (8, 8, 7),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "gpt-5-nano",
        context: 400_000,
        max_output: 128_000,
        tier: PricingTier::Low,
        ability: (7, 7, 7),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "gpt-5",
        context: 400_000,
        max_output: 128_000,
        tier: PricingTier::High,
        ability: (9, 9, 8),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "o3-mini",
        context: 200_000,
        max_output: 100_000,
        tier: PricingTier::Medium,
        ability: (8, 8, 6),
        tools: true,
        vision: false,
    },
    Family {
        prefix: "o3",
        context: 200_000,
        max_output: 100_000,
        tier: PricingTier::High,
        ability: (9, 9, 7),
        tools: true,
        vision: true,
    },
    Family {
        prefix: "o4-mini",
        context: 200_000,
        max_output: 100_000,
        tier: PricingTier::Medium,
        ability: (8, 8, 7),
        tools: true,
        vision: true,
    },
];

pub fn pricing_tier(prompt_price: f64) -> PricingTier {
    OPENROUTER_ABILITY
        .iter()
        .find_map(|(threshold, tier)| (prompt_price <= *threshold).then_some(*tier))
        .unwrap_or(PricingTier::Frontier)
}

pub fn map_openrouter_model(raw: &Value) -> Result<ModelEntry, RefreshError> {
    map_openrouter_model_on(raw, Local::now().date_naive())
}

pub fn map_openrouter_model_on(raw: &Value, today: NaiveDate) -> Result<ModelEntry, RefreshError> {
    let model_id = raw.get("id");
    let context = raw.get("context_length");
    let context = context.and_then(python_integer);
    if !model_id.is_some_and(truthy)
        || !context
            .as_ref()
            .is_some_and(agentrouter_core::pydantic_integer_is_positive)
    {
        return Err(RefreshError(format!(
            "entry missing id/context_length: {}",
            model_id
                .map(python_repr)
                .unwrap_or_else(|| python_repr(raw))
        )));
    }
    let context_window = context.expect("validated above");

    let pricing = match raw.get("pricing").filter(|value| truthy(value)) {
        None => None,
        Some(Value::Object(map)) => map.get("prompt"),
        Some(_) => return Err(RefreshError("pricing must be a mapping".into())),
    };
    let prompt_price = match pricing {
        None => 0.0,
        Some(value) => python_float(value).map_err(|error| {
            RefreshError(format!(
                "entry '{}': unparseable pricing: {error}",
                python_text(model_id.unwrap())
            ))
        })?,
    };
    let tier = pricing_tier(prompt_price);
    let score = match tier {
        PricingTier::Free => 5,
        PricingTier::Low => 6,
        PricingTier::Medium => 7,
        PricingTier::High => 8,
        PricingTier::Frontier => 9,
    };
    let tools = if has_member(raw.get("supported_parameters"), "tools") {
        vec!["tool-use".to_string(), "function-calling".to_string()]
    } else {
        Vec::new()
    };
    let vision = raw
        .get("architecture")
        .and_then(|value| value.get("input_modalities"))
        .is_some_and(|value| has_member(Some(value), "image"));
    let max_out = raw
        .get("top_provider")
        .and_then(|value| value.get("max_completion_tokens"))
        .and_then(python_integer)
        .filter(agentrouter_core::pydantic_integer_is_positive)
        .unwrap_or_else(|| {
            let derived = agentrouter_core::pydantic_integer_div_small_floor(&context_window, 4);
            if agentrouter_core::pydantic_integer_cmp(&derived, &1024.into()).is_lt() {
                1024.into()
            } else {
                derived
            }
        });

    let model_id = model_id
        .and_then(Value::as_str)
        .ok_or_else(|| RefreshError("model id must be a string".into()))?;
    let display_name = match raw.get("name") {
        None | Some(Value::Null) => None,
        Some(Value::String(value)) => Some(value.clone()),
        Some(_) => return Err(RefreshError("display_name must be a string".into())),
    };
    Ok(make_entry(
        EntryData {
            provider: "openrouter",
            model_id,
            display_name,
            context_window,
            max_output_tokens: max_out,
            pricing_tier: tier,
            ability_scores: (score, score, score),
            tool_support: tools,
            vision_support: vision,
            notes: "auto-generated by providers refresh; ability scores are a pricing-based heuristic, not benchmarks",
        },
        today,
    ))
}

pub fn map_openai_model(raw: &Value) -> Result<ModelEntry, RefreshError> {
    map_openai_model_on(raw, Local::now().date_naive())
}

pub fn map_openai_model_on(raw: &Value, today: NaiveDate) -> Result<ModelEntry, RefreshError> {
    let model_id = raw
        .get("id")
        .and_then(Value::as_str)
        .filter(|id| !id.is_empty())
        .ok_or_else(|| RefreshError(format!("entry missing id: {}", python_repr(raw))))?;
    let family = OPENAI_FAMILIES
        .iter()
        .filter(|family| {
            model_id == family.prefix
                || model_id
                    .strip_prefix(family.prefix)
                    .is_some_and(|suffix| suffix.starts_with('-'))
        })
        .max_by_key(|family| family.prefix.len())
        .ok_or_else(|| RefreshError(format!("no family mapping for '{model_id}'")))?;
    let tools = if family.tools {
        vec!["tool-use".to_string(), "function-calling".to_string()]
    } else {
        Vec::new()
    };
    Ok(make_entry(
        EntryData {
            provider: "openai",
            model_id,
            display_name: None,
            context_window: family.context.into(),
            max_output_tokens: family.max_output.into(),
            pricing_tier: family.tier,
            ability_scores: family.ability,
            tool_support: tools,
            vision_support: family.vision,
            notes: "auto-generated by providers refresh; metadata from a static family table, not benchmarks",
        },
        today,
    ))
}

pub fn openrouter_from_payload(
    payload: &Value,
    limit: usize,
    match_id: Option<&str>,
    today: NaiveDate,
) -> Result<(Vec<ModelEntry>, Vec<String>), RefreshError> {
    let data = payload
        .get("data")
        .and_then(Value::as_array)
        .filter(|items| !items.is_empty())
        .ok_or_else(|| {
            RefreshError(
                "unexpected response shape from OpenRouter: expected a non-empty 'data' list"
                    .into(),
            )
        })?;
    let mut entries = Vec::new();
    let mut warnings = Vec::new();
    for raw in data {
        if entries.len() >= limit {
            break;
        }
        let id = raw.get("id").map(python_text).unwrap_or_default();
        if match_id.is_some_and(|needle| !id.contains(needle)) {
            continue;
        }
        match map_openrouter_model_on(raw, today) {
            Ok(entry) => entries.push(entry),
            Err(error) => warnings.push(format!("skipped: {error}")),
        }
    }
    if entries.is_empty() {
        return Err(RefreshError(no_entries_message("OpenRouter", match_id)));
    }
    Ok((entries, warnings))
}

pub fn openai_from_payload(
    payload: &Value,
    limit: usize,
    match_id: Option<&str>,
    today: NaiveDate,
) -> Result<(Vec<ModelEntry>, Vec<String>), RefreshError> {
    let data = payload
        .get("data")
        .and_then(Value::as_array)
        .filter(|items| !items.is_empty())
        .ok_or_else(|| {
            RefreshError(
                "unexpected response shape from OpenAI: expected a non-empty 'data' list".into(),
            )
        })?;
    let mut entries = Vec::new();
    let mut unmapped = 0;
    for raw in data {
        if entries.len() >= limit {
            break;
        }
        let id = raw.get("id").map(python_text).unwrap_or_default();
        if match_id.is_some_and(|needle| !id.contains(needle)) {
            continue;
        }
        match map_openai_model_on(raw, today) {
            Ok(entry) => entries.push(entry),
            Err(_) => unmapped += 1,
        }
    }
    let warnings = if unmapped > 0 {
        vec![format!(
            "skipped {unmapped} catalog entries with no family mapping (non-chat or unknown)"
        )]
    } else {
        Vec::new()
    };
    if entries.is_empty() {
        return Err(RefreshError(no_entries_message("OpenAI", match_id)));
    }
    Ok((entries, warnings))
}

fn no_entries_message(provider: &str, match_id: Option<&str>) -> String {
    match match_id {
        Some(match_id) => format!("no {provider} entry matched '--match {match_id}'"),
        None => format!("no {provider} entry could be mapped to the registry schema"),
    }
}

fn make_entry(data: EntryData<'_>, today: NaiveDate) -> ModelEntry {
    ModelEntry {
        provider: data.provider.into(),
        vendor: Some(data.provider.into()),
        model_id: data.model_id.into(),
        display_name: data.display_name,
        family: None,
        release_channel: ReleaseChannel::Stable,
        snapshot_type: SnapshotType::Unknown,
        context_window: data.context_window,
        max_input_tokens: None,
        max_output_tokens: data.max_output_tokens,
        pricing_tier: data.pricing_tier,
        latency_tier: LatencyTier::Medium,
        input_price_per_million: None,
        output_price_per_million: None,
        pricing_basis: None,
        pricing_effective_date: None,
        ability: Ability {
            coding: data.ability_scores.0,
            reasoning: data.ability_scores.1,
            writing: data.ability_scores.2,
        },
        ability_source: AbilitySource::Heuristic,
        ability_confidence: None,
        tool_support: data.tool_support,
        vision_support: data.vision_support,
        audio_support: false,
        video_support: false,
        reasoning_support: false,
        ideal_use_cases: Vec::new(),
        avoid_use_cases: Vec::new(),
        deprecation_status: DeprecationStatus::Active,
        fallback: Vec::new(),
        execution_targets: Vec::new(),
        notes: Some(data.notes.into()),
        source: Some("refresh".into()),
        source_url_or_identifier: None,
        last_updated: Some(today.format("%Y-%m-%d").to_string()),
        last_verified: None,
    }
}

fn python_integer(value: &Value) -> Option<serde_json::Number> {
    match value {
        Value::Number(number) if super::is_integer_number_text(&number.to_string()) => {
            Some(number.clone())
        }
        Value::Bool(value) => Some(u8::from(*value).into()),
        _ => None,
    }
}

fn python_float(value: &Value) -> Result<f64, String> {
    match value {
        Value::Number(number) => number
            .as_f64()
            .ok_or_else(|| "number is outside the supported float range".into()),
        Value::String(value) => value.parse::<f64>().map_err(|error| error.to_string()),
        Value::Bool(value) => Ok(if *value { 1.0 } else { 0.0 }),
        Value::Null => {
            Err("float() argument must be a string or a real number, not 'NoneType'".into())
        }
        _ => Err("float() argument must be a string or a real number".into()),
    }
}

fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(value) => value.as_f64().is_some_and(|value| value != 0.0),
        Value::String(value) => !value.is_empty(),
        Value::Array(value) => !value.is_empty(),
        Value::Object(value) => !value.is_empty(),
    }
}

fn has_member(value: Option<&Value>, needle: &str) -> bool {
    match value {
        Some(Value::Array(items)) => items.iter().any(|item| item.as_str() == Some(needle)),
        Some(Value::Object(items)) => items.contains_key(needle),
        Some(Value::String(value)) => value.contains(needle),
        _ => false,
    }
}

fn python_text(value: &Value) -> String {
    match value {
        Value::String(value) => value.clone(),
        _ => value.to_string(),
    }
}

fn python_repr(value: &Value) -> String {
    match value {
        Value::String(value) => format!("'{value}'"),
        _ => value.to_string(),
    }
}
