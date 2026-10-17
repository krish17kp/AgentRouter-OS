//! Strict, offline YAML registry loader for AgentRouter OS.
//!
//! Mirrors the Python registry's required fields, defaults, provider reference
//! checks, duplicate-key rejection and non-fatal unresolved fallback warnings.
//! The Python implementation remains authoritative during the migration.

use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

use agentrouter_core::PricingTier;
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum RegistryError {
    #[error("could not read registry file: {0}")]
    Io(#[from] std::io::Error),
    #[error("invalid registry YAML: {0}")]
    Yaml(#[from] serde_yaml::Error),
    #[error("{0}")]
    Invalid(String),
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Provider {
    pub id: String,
    pub adapter: String,
    #[serde(default = "default_auth")]
    pub auth_model: String,
    #[serde(default)]
    pub supports_execution: bool,
    #[serde(default)]
    pub exec_command: Vec<String>,
}

fn default_auth() -> String {
    "none".to_owned()
}

#[derive(Debug, Deserialize)]
struct ProvidersFile {
    #[serde(default)]
    providers: Vec<Provider>,
}

pub fn parse_providers(yaml: &str) -> Result<BTreeMap<String, Provider>, RegistryError> {
    let parsed: ProvidersFile = serde_yaml::from_str(yaml)?;
    let mut providers = BTreeMap::new();
    // Keep Python's duplicate-provider behavior: later definitions replace
    // earlier ones. Model identifiers, in contrast, MUST be unique.
    for provider in parsed.providers {
        providers.insert(provider.id.clone(), provider);
    }
    if providers.is_empty() {
        return Err(RegistryError::Invalid("no providers defined".to_owned()));
    }
    Ok(providers)
}

pub fn load_providers(path: impl AsRef<Path>) -> Result<BTreeMap<String, Provider>, RegistryError> {
    parse_providers(&fs::read_to_string(path)?)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LatencyTier {
    Fast,
    Medium,
    Slow,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DeprecationStatus {
    Active,
    Deprecated,
    Retired,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReleaseChannel {
    #[default]
    Stable,
    Preview,
    Experimental,
    Deprecated,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SnapshotType {
    Pinned,
    Alias,
    #[default]
    Unknown,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AbilitySource {
    Official,
    Benchmark,
    Curated,
    #[default]
    Heuristic,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionMode {
    #[default]
    Cli,
    Api,
    Manual,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Ability {
    pub coding: i32,
    pub reasoning: i32,
    pub writing: i32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutionTarget {
    pub host: String,
    pub host_model_id: String,
    #[serde(default)]
    pub execution_mode: ExecutionMode,
    #[serde(default)]
    pub command_template: Option<Vec<String>>,
    #[serde(default)]
    pub required_command: Option<String>,
    #[serde(default)]
    pub required_env: Vec<String>,
    #[serde(default = "default_true")]
    pub supports_noninteractive: bool,
    #[serde(default)]
    pub supports_file_edit: bool,
    #[serde(default)]
    pub supports_shell: bool,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ModelEntry {
    pub provider: String,
    #[serde(default)]
    pub vendor: Option<String>,
    pub model_id: String,
    #[serde(default)]
    pub display_name: Option<String>,
    #[serde(default)]
    pub family: Option<String>,
    #[serde(default)]
    pub release_channel: ReleaseChannel,
    #[serde(default)]
    pub snapshot_type: SnapshotType,
    pub context_window: u64,
    #[serde(default)]
    pub max_input_tokens: Option<u64>,
    pub max_output_tokens: u64,
    pub pricing_tier: PricingTier,
    pub latency_tier: LatencyTier,
    #[serde(default)]
    pub input_price_per_million: Option<f64>,
    #[serde(default)]
    pub output_price_per_million: Option<f64>,
    #[serde(default)]
    pub pricing_basis: Option<String>,
    #[serde(default)]
    pub pricing_effective_date: Option<String>,
    pub ability: Ability,
    #[serde(default)]
    pub ability_source: AbilitySource,
    #[serde(default)]
    pub ability_confidence: Option<f64>,
    pub tool_support: Vec<String>,
    pub vision_support: bool,
    #[serde(default)]
    pub audio_support: bool,
    #[serde(default)]
    pub video_support: bool,
    #[serde(default)]
    pub reasoning_support: bool,
    #[serde(default)]
    pub ideal_use_cases: Vec<String>,
    #[serde(default)]
    pub avoid_use_cases: Vec<String>,
    pub deprecation_status: DeprecationStatus,
    #[serde(default)]
    pub fallback: Vec<String>,
    #[serde(default)]
    pub execution_targets: Vec<ExecutionTarget>,
    #[serde(default)]
    pub notes: Option<String>,
    #[serde(default)]
    pub source: Option<String>,
    #[serde(default)]
    pub source_url_or_identifier: Option<String>,
    #[serde(default)]
    pub last_updated: Option<String>,
    #[serde(default)]
    pub last_verified: Option<String>,
}

impl ModelEntry {
    pub fn key(&self) -> String {
        format!("{}/{}", self.provider, self.model_id)
    }

    pub fn vendor_key(&self) -> String {
        format!(
            "{}/{}",
            self.vendor.as_deref().unwrap_or(&self.provider),
            self.model_id
        )
    }

    pub fn name(&self) -> &str {
        self.display_name.as_deref().unwrap_or(&self.model_id)
    }
}

#[derive(Debug, Deserialize)]
struct ModelsFile {
    #[serde(default)]
    models: Vec<ModelEntry>,
}

fn validate_date(date: &str) -> bool {
    let bytes = date.as_bytes();
    if bytes.len() != 10 || bytes[4] != b'-' || bytes[7] != b'-' {
        return false;
    }
    if !bytes
        .iter()
        .enumerate()
        .all(|(i, b)| i == 4 || i == 7 || b.is_ascii_digit())
    {
        return false;
    }
    let year: u32 = date[0..4].parse().unwrap_or(0);
    let month: u32 = date[5..7].parse().unwrap_or(0);
    let day: u32 = date[8..10].parse().unwrap_or(0);
    if year == 0 {
        return false;
    }
    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let max_day = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if leap => 29,
        2 => 28,
        _ => return false,
    };
    (1..=max_day).contains(&day)
}

fn validate_model(model: &ModelEntry) -> Result<(), RegistryError> {
    let invalid = |detail: &str| {
        RegistryError::Invalid(format!("model '{}': {}", model.key(), detail))
    };
    if model.context_window == 0 {
        return Err(invalid("context_window must be positive"));
    }
    if model.max_output_tokens == 0 {
        return Err(invalid("max_output_tokens must be positive"));
    }
    if model.max_input_tokens == Some(0) {
        return Err(invalid("max_input_tokens must be positive"));
    }
    if [model.ability.coding, model.ability.reasoning, model.ability.writing]
        .iter()
        .any(|v| !(0..=10).contains(v))
    {
        return Err(invalid("ability scores must be between 0 and 10"));
    }
    if let Some(confidence) = model.ability_confidence {
        if !confidence.is_finite() || !(0.0..=1.0).contains(&confidence) {
            return Err(invalid("ability_confidence must be between 0 and 1"));
        }
    }
    for (name, value) in [
        ("input_price_per_million", model.input_price_per_million),
        ("output_price_per_million", model.output_price_per_million),
    ] {
        if let Some(price) = value {
            if !price.is_finite() || price < 0.0 {
                return Err(invalid(&format!("{name} must be nonnegative")));
            }
        }
    }
    for (name, value) in [
        ("last_updated", model.last_updated.as_deref()),
        ("last_verified", model.last_verified.as_deref()),
        ("pricing_effective_date", model.pricing_effective_date.as_deref()),
    ] {
        if let Some(date) = value {
            if !validate_date(date) {
                return Err(invalid(&format!("{name} must be a valid ISO date")));
            }
        }
    }
    Ok(())
}

/// Python-compatible load_models subset: no staleness warning here.
/// Staleness, generated registries, and ability overrides belong in
/// load_all_models, a separate R2 milestone still to be implemented.
pub fn parse_models(
    yaml: &str,
    providers: &BTreeMap<String, Provider>,
) -> Result<(Vec<ModelEntry>, Vec<String>), RegistryError> {
    let parsed: ModelsFile = serde_yaml::from_str(yaml)?;
    if parsed.models.is_empty() {
        return Err(RegistryError::Invalid("no models defined".to_owned()));
    }

    let mut models = Vec::with_capacity(parsed.models.len());
    let mut seen = HashSet::new();
    for mut model in parsed.models {
        validate_model(&model)?;
        if !providers.contains_key(&model.provider) {
            return Err(RegistryError::Invalid(format!(
                "model '{}' references unknown provider '{}'",
                model.model_id, model.provider
            )));
        }
        let key = model.key();
        if !seen.insert(key.clone()) {
            return Err(RegistryError::Invalid(format!(
                "duplicate model '{key}'"
            )));
        }
        // Pydantic's model_validator defaults vendor to provider on load.
        if model.vendor.is_none() {
            model.vendor = Some(model.provider.clone());
        }
        models.push(model);
    }

    let known_ids: HashSet<&str> = models.iter().map(|m| m.model_id.as_str()).collect();
    let warnings = models
        .iter()
        .flat_map(|m| {
            m.fallback
                .iter()
                .filter(|fb| !known_ids.contains(fb.as_str()))
                .map(move |fb| {
                    format!(
                        "model '{}': fallback '{}' does not resolve to a known model_id",
                        m.model_id, fb
                    )
                })
        })
        .collect();
    Ok((models, warnings))
}

pub fn load_models(
    path: impl AsRef<Path>,
    providers: &BTreeMap<String, Provider>,
) -> Result<(Vec<ModelEntry>, Vec<String>), RegistryError> {
    parse_models(&fs::read_to_string(path)?, providers)
}

#[cfg(test)]
mod tests {
    use super::*;

    const PROVIDERS: &str = include_str!("../../../agentrouter/seeds/providers.yaml");
    const MODELS: &str = include_str!("../../../agentrouter/seeds/models.yaml");

    fn sample() -> String {
        r#"models:
  - provider: openai
    model_id: sample
    context_window: 12345
    max_output_tokens: 1024
    pricing_tier: low
    latency_tier: fast
    ability: {coding: 8, reasoning: 7, writing: 6}
    tool_support: []
    vision_support: false
    deprecation_status: active
"#
        .to_owned()
    }

    #[test]
    fn seed_files_load_with_no_unresolved_fallbacks() {
        let providers = parse_providers(PROVIDERS).unwrap();
        let (models, warnings) = parse_models(MODELS, &providers).unwrap();
        assert!(!models.is_empty());
        assert!(warnings.is_empty(), "{warnings:?}");
        assert!(models.iter().all(|m| m.vendor.is_some()));
        assert!(providers.values().all(|p| !p.supports_execution));
    }

    #[test]
    fn missing_context_window_and_unknown_fields_fail_closed() {
        let providers = parse_providers(PROVIDERS).unwrap();
        let missing = sample().replace("    context_window: 12345\n", "");
        assert!(parse_models(&missing, &providers)
            .unwrap_err()
            .to_string()
            .contains("context_window"));
        let unknown = sample().replace("    model_id: sample", "    surprise_field: 1\n    model_id: sample");
        assert!(parse_models(&unknown, &providers).is_err());
    }

    #[test]
    fn rejects_invalid_provider_duplicate_model_and_bounds() {
        let providers = parse_providers(PROVIDERS).unwrap();
        assert!(parse_models(&sample().replace("openai", "not-installed"), &providers).is_err());
        assert!(parse_models(&(sample() + &sample().replace("models:\n", "")), &providers).is_err());
        assert!(parse_models(&sample().replace("12345", "0"), &providers).is_err());
        assert!(parse_models(&sample().replace("coding: 8", "coding: 11"), &providers).is_err());
        assert!(parse_models(&sample().replace("low", "not-a-tier"), &providers).is_err());
    }

    #[test]
    fn warns_but_loads_unresolved_fallback_and_defaults_vendor() {
        let providers = parse_providers(PROVIDERS).unwrap();
        let yaml = sample().replace("    model_id: sample", "    model_id: sample\n    fallback: [future-model]");
        let (models, warnings) = parse_models(&yaml, &providers).unwrap();
        assert_eq!(models[0].vendor.as_deref(), Some("openai"));
        assert_eq!(models[0].key(), "openai/sample");
        assert_eq!(models[0].name(), "sample");
        assert_eq!(warnings.len(), 1);
        assert!(warnings[0].contains("future-model"));
    }

    #[test]
    fn dates_validate_gregorian_days() {
        assert!(validate_date("2026-07-14"));
        assert!(validate_date("2024-02-29"));
        assert!(!validate_date("2026-02-29"));
        assert!(!validate_date("2026-13-01"));
        assert!(!validate_date("2026-01-00"));
    }
}
