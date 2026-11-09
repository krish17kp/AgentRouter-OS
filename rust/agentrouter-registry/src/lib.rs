//! Offline YAML registry parsing and validation. This mirrors the core
//! fail-closed `agentrouter.registry.load_models/load_providers` boundary.
use agentrouter_core::{DeprecationStatus, LatencyTier, PricingTier};
use chrono::{Duration, NaiveDate};
use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum RegistryError {
    #[error("invalid YAML: {0}")]
    Yaml(#[from] serde_yaml::Error),
    #[error("invalid registry: {0}")]
    Invalid(String),
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Provider {
    pub id: String,
    pub adapter: String,
    #[serde(default = "default_auth_model")]
    pub auth_model: String,
    #[serde(default)]
    pub supports_execution: bool,
    #[serde(default)]
    pub exec_command: Vec<String>,
}

fn default_auth_model() -> String {
    "none".to_owned()
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Ability {
    pub coding: u8,
    pub reasoning: u8,
    pub writing: u8,
}

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReleaseChannel {
    #[default]
    Stable,
    Preview,
    Experimental,
    Deprecated,
}
#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SnapshotType {
    Pinned,
    Alias,
    #[default]
    Unknown,
}

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AbilitySource {
    Official,
    Benchmark,
    Curated,
    #[default]
    Heuristic,
}

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionMode {
    #[default]
    Cli,
    Api,
    Manual,
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
    pub pricing_effective_date: Option<NaiveDate>,
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
    pub last_updated: Option<NaiveDate>,
    #[serde(default)]
    pub last_verified: Option<NaiveDate>,
}

impl ModelEntry {
    pub fn key(&self) -> String {
        format!("{}/{}", self.provider, self.model_id)
    }
    pub fn vendor(&self) -> &str {
        self.vendor.as_deref().unwrap_or(&self.provider)
    }
    fn validate(&self) -> Result<(), RegistryError> {
        if self.context_window == 0
            || self.max_output_tokens == 0
            || self.max_input_tokens == Some(0)
        {
            return Err(RegistryError::Invalid(format!(
                "{}: token limits must be positive",
                self.key()
            )));
        }
        if self.ability.coding > 10 || self.ability.reasoning > 10 || self.ability.writing > 10 {
            return Err(RegistryError::Invalid(format!(
                "{}: ability must be 0..10",
                self.key()
            )));
        }
        if self
            .ability_confidence
            .is_some_and(|v| !(0.0..=1.0).contains(&v))
        {
            return Err(RegistryError::Invalid(format!(
                "{}: ability confidence must be 0..1",
                self.key()
            )));
        }
        if self
            .input_price_per_million
            .is_some_and(|v| !v.is_finite() || v < 0.0)
            || self
                .output_price_per_million
                .is_some_and(|v| !v.is_finite() || v < 0.0)
        {
            return Err(RegistryError::Invalid(format!(
                "{}: prices must be finite and nonnegative",
                self.key()
            )));
        }
        Ok(())
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ProviderFile {
    providers: Vec<Provider>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ModelFile {
    models: Vec<ModelEntry>,
}

pub fn load_providers(text: &str) -> Result<Vec<Provider>, RegistryError> {
    let file: ProviderFile = serde_yaml::from_str(text)?;
    if file.providers.is_empty() {
        return Err(RegistryError::Invalid("no providers defined".to_owned()));
    }
    Ok(file.providers)
}

pub fn load_models(
    text: &str,
    providers: &[Provider],
) -> Result<(Vec<ModelEntry>, Vec<String>), RegistryError> {
    let file: ModelFile = serde_yaml::from_str(text)?;
    if file.models.is_empty() {
        return Err(RegistryError::Invalid("no models defined".to_owned()));
    }
    let known_providers: HashSet<&str> = providers.iter().map(|p| p.id.as_str()).collect();
    let mut seen = HashSet::new();
    for model in &file.models {
        model.validate()?;
        if !known_providers.contains(model.provider.as_str()) {
            return Err(RegistryError::Invalid(format!(
                "{}: unknown provider",
                model.key()
            )));
        }
        if !seen.insert(model.key()) {
            return Err(RegistryError::Invalid(format!(
                "{}: duplicate model",
                model.key()
            )));
        }
    }
    let known_ids: HashSet<&str> = file.models.iter().map(|m| m.model_id.as_str()).collect();
    let warnings = file
        .models
        .iter()
        .flat_map(|model| {
            model.fallback.iter().filter_map(|fb| {
                if known_ids.contains(fb.as_str()) {
                    None
                } else {
                    Some(format!(
                        "model '{}': fallback '{}' does not resolve to a known model_id",
                        model.model_id, fb
                    ))
                }
            })
        })
        .collect();
    Ok((file.models, warnings))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct AbilityOverride {
    #[serde(default)]
    coding: Option<u8>,
    #[serde(default)]
    reasoning: Option<u8>,
    #[serde(default)]
    writing: Option<u8>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct OverrideFile {
    overrides: IndexMap<String, Option<AbilityOverride>>,
}

/// Merge manual and generated registries; manual entries win on key collision.
/// `generated` is `(filename, YAML)` and is sorted like Python's `glob` result.
pub fn load_all_models(
    manual_yaml: &str,
    generated: &[(String, String)],
    overrides_yaml: Option<&str>,
    providers: &[Provider],
    today: NaiveDate,
) -> Result<(Vec<ModelEntry>, Vec<String>), RegistryError> {
    let (mut models, mut warnings) = load_models(manual_yaml, providers)?;
    let mut seen: HashSet<String> = models.iter().map(ModelEntry::key).collect();
    let mut sorted = generated.to_vec();
    sorted.sort_by(|a, b| a.0.cmp(&b.0));
    for (filename, text) in sorted {
        let (generated_models, generated_warnings) = load_models(&text, providers)?;
        warnings.extend(generated_warnings);
        for model in generated_models {
            let key = model.key();
            if seen.insert(key.clone()) {
                models.push(model);
            } else {
                warnings.push(format!(
                    "{filename}: '{key}' shadowed by manual models.yaml"
                ));
            }
        }
    }
    if let Some(text) = overrides_yaml {
        let file: OverrideFile = serde_yaml::from_str(text)?;
        let by_key: HashMap<String, usize> = models
            .iter()
            .enumerate()
            .map(|(i, m)| (m.key(), i))
            .collect();
        for (key, scores) in file.overrides {
            if let Some(&index) = by_key.get(&key) {
                if let Some(scores) = scores {
                    let ability = &mut models[index].ability;
                    if let Some(value) = scores.coding {
                        ability.coding = value;
                    }
                    if let Some(value) = scores.reasoning {
                        ability.reasoning = value;
                    }
                    if let Some(value) = scores.writing {
                        ability.writing = value;
                    }
                    models[index].validate()?;
                }
            } else {
                warnings.push(format!(
                    "ability_overrides.yaml: '{key}' does not match any loaded model - ignored"
                ));
            }
        }
    }
    let stale_cutoff = today - Duration::days(90);
    let stale: Vec<String> = models
        .iter()
        .filter(|m| m.last_updated.is_some_and(|date| date < stale_cutoff))
        .map(ModelEntry::key)
        .collect();
    if let Some(first) = stale.first() {
        warnings.push(format!("{} model(s) have last_updated older than 90 days (e.g. {}) - consider 'agentrouter providers refresh' or updating models.yaml", stale.len(), first));
    }
    Ok((models, warnings))
}
