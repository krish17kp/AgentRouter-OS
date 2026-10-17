//! Rust port of `agentrouter/registry.py` + the registry-entry models from
//! `agentrouter/schema.py`. Field names, YAML shapes, and error conditions
//! mirror the Python module exactly — this is the contract the Python/Rust
//! compatibility test in `tests/` checks against the real seed registries.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use thiserror::Error;

pub use agentrouter_core::PricingTier;

const STALE_AFTER_DAYS: i64 = 90;
const OVERRIDES_FILE: &str = "ability_overrides.yaml";

/// Mirrors `agentrouter.registry.RegistryError` — the CLI maps this to exit
/// code 3. One variant per distinct Python `RegistryError(f"...")` site so
/// callers can match on failure kind without string-parsing the message.
#[derive(Debug, Error)]
pub enum RegistryError {
    #[error("Registry file not found: {0} (run: agentrouter init)")]
    NotFound(PathBuf),
    #[error("Invalid YAML in {0}: {1}")]
    InvalidYaml(PathBuf, String),
    #[error("{0}: expected a mapping at top level")]
    NotAMapping(PathBuf),
    #[error("{path}: providers[{index}] invalid: {reason}")]
    InvalidProvider {
        path: PathBuf,
        index: usize,
        reason: String,
    },
    #[error("{0}: no providers defined")]
    NoProviders(PathBuf),
    #[error("{path}: model '{model}' invalid: {reason}")]
    InvalidModel {
        path: PathBuf,
        model: String,
        reason: String,
    },
    #[error("{path}: model '{model}' references unknown provider '{provider}'")]
    UnknownProvider {
        path: PathBuf,
        model: String,
        provider: String,
    },
    #[error("{0}: no models defined")]
    NoModels(PathBuf),
    #[error("{path}: duplicate model '{key}'")]
    DuplicateModel { path: PathBuf, key: String },
    #[error("{0}: expected an 'overrides' mapping of model key -> scores")]
    OverridesNotAMapping(PathBuf),
    #[error("{path}: override for '{key}' invalid: {reason}")]
    InvalidOverride {
        path: PathBuf,
        key: String,
        reason: String,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LatencyTier {
    Fast,
    Medium,
    Slow,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DeprecationStatus {
    Active,
    Deprecated,
    Retired,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReleaseChannel {
    Stable,
    Preview,
    Experimental,
    Deprecated,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SnapshotType {
    Pinned,
    Alias,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AbilitySource {
    Official,
    Benchmark,
    Curated,
    Heuristic,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionMode {
    Cli,
    Api,
    Manual,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Ability {
    pub coding: u8,
    pub reasoning: u8,
    pub writing: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutionTarget {
    pub host: String,
    pub host_model_id: String,
    #[serde(default = "default_execution_mode")]
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

fn default_execution_mode() -> ExecutionMode {
    ExecutionMode::Cli
}

fn default_true() -> bool {
    true
}

/// Mirrors `schema.ModelEntry`. `vendor` defaults to `provider` (the Python
/// `_default_vendor` validator) via [`ModelEntry::vendor`] rather than a
/// serde default, since the default depends on another field's value.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelEntry {
    pub provider: String,
    #[serde(default)]
    vendor: Option<String>,
    pub model_id: String,
    pub display_name: Option<String>,
    pub family: Option<String>,
    #[serde(default = "default_release_channel")]
    pub release_channel: ReleaseChannel,
    #[serde(default = "default_snapshot_type")]
    pub snapshot_type: SnapshotType,
    pub context_window: u32,
    pub max_input_tokens: Option<u32>,
    pub max_output_tokens: u32,
    pub pricing_tier: PricingTier,
    pub latency_tier: LatencyTier,
    pub input_price_per_million: Option<f64>,
    pub output_price_per_million: Option<f64>,
    pub pricing_basis: Option<String>,
    pub pricing_effective_date: Option<String>,
    pub ability: Ability,
    #[serde(default = "default_ability_source")]
    pub ability_source: AbilitySource,
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
    pub notes: Option<String>,
    pub source: Option<String>,
    pub source_url_or_identifier: Option<String>,
    /// ISO `YYYY-MM-DD`, kept as a string field (matching the raw YAML
    /// scalar) and parsed on demand in [`ModelEntry::last_updated_date`] —
    /// avoids pulling a YAML-date serde adapter in for one staleness check.
    pub last_updated: Option<String>,
    pub last_verified: Option<String>,
}

fn default_release_channel() -> ReleaseChannel {
    ReleaseChannel::Stable
}
fn default_snapshot_type() -> SnapshotType {
    SnapshotType::Unknown
}
fn default_ability_source() -> AbilitySource {
    AbilitySource::Heuristic
}

impl ModelEntry {
    pub fn vendor(&self) -> &str {
        self.vendor.as_deref().unwrap_or(&self.provider)
    }

    pub fn key(&self) -> String {
        format!("{}/{}", self.provider, self.model_id)
    }

    pub fn vendor_key(&self) -> String {
        format!("{}/{}", self.vendor(), self.model_id)
    }

    pub fn name(&self) -> &str {
        self.display_name.as_deref().unwrap_or(&self.model_id)
    }

    pub fn last_updated_date(&self) -> Option<NaiveDate> {
        self.last_updated
            .as_deref()
            .and_then(|s| NaiveDate::parse_from_str(s, "%Y-%m-%d").ok())
    }
}

#[derive(Debug, Clone, Deserialize)]
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
    "none".to_string()
}

fn load_yaml(path: &Path) -> Result<serde_yaml::Mapping, RegistryError> {
    if !path.exists() {
        return Err(RegistryError::NotFound(path.to_path_buf()));
    }
    let text = std::fs::read_to_string(path)
        .map_err(|e| RegistryError::InvalidYaml(path.to_path_buf(), e.to_string()))?;
    let value: serde_yaml::Value = serde_yaml::from_str(&text)
        .map_err(|e| RegistryError::InvalidYaml(path.to_path_buf(), e.to_string()))?;
    value
        .as_mapping()
        .cloned()
        .ok_or_else(|| RegistryError::NotAMapping(path.to_path_buf()))
}

fn seq_field(map: &serde_yaml::Mapping, key: &str) -> Vec<serde_yaml::Value> {
    map.get(serde_yaml::Value::String(key.to_string()))
        .and_then(|v| v.as_sequence().cloned())
        .unwrap_or_default()
}

pub fn load_providers(path: &Path) -> Result<HashMap<String, Provider>, RegistryError> {
    let data = load_yaml(path)?;
    let mut providers = HashMap::new();
    for (i, raw) in seq_field(&data, "providers").into_iter().enumerate() {
        let p: Provider =
            serde_yaml::from_value(raw).map_err(|e| RegistryError::InvalidProvider {
                path: path.to_path_buf(),
                index: i,
                reason: e.to_string(),
            })?;
        providers.insert(p.id.clone(), p);
    }
    if providers.is_empty() {
        return Err(RegistryError::NoProviders(path.to_path_buf()));
    }
    Ok(providers)
}

/// Returns `(models, warnings)` — unresolved fallbacks warn, bad fields fail,
/// matching `agentrouter.registry.load_models` exactly.
pub fn load_models(
    path: &Path,
    providers: &HashMap<String, Provider>,
) -> Result<(Vec<ModelEntry>, Vec<String>), RegistryError> {
    let data = load_yaml(path)?;
    let mut models = Vec::new();
    for raw in seq_field(&data, "models") {
        let fallback_id = raw
            .as_mapping()
            .and_then(|m| m.get(serde_yaml::Value::String("model_id".to_string())))
            .and_then(|v| v.as_str())
            .unwrap_or("<unknown>")
            .to_string();
        let m: ModelEntry =
            serde_yaml::from_value(raw).map_err(|e| RegistryError::InvalidModel {
                path: path.to_path_buf(),
                model: fallback_id,
                reason: e.to_string(),
            })?;
        if !providers.contains_key(&m.provider) {
            return Err(RegistryError::UnknownProvider {
                path: path.to_path_buf(),
                model: m.model_id.clone(),
                provider: m.provider.clone(),
            });
        }
        models.push(m);
    }
    if models.is_empty() {
        return Err(RegistryError::NoModels(path.to_path_buf()));
    }

    let mut seen = HashSet::new();
    for m in &models {
        if !seen.insert(m.key()) {
            return Err(RegistryError::DuplicateModel {
                path: path.to_path_buf(),
                key: m.key(),
            });
        }
    }

    let known_ids: HashSet<&str> = models.iter().map(|m| m.model_id.as_str()).collect();
    let mut warnings = Vec::new();
    for m in &models {
        for fb in &m.fallback {
            if !known_ids.contains(fb.as_str()) {
                warnings.push(format!(
                    "model '{}': fallback '{}' does not resolve to a known model_id",
                    m.model_id, fb
                ));
            }
        }
    }
    Ok((models, warnings))
}

/// Manual `models.yaml` + any `models.*.generated.yaml`, then curated
/// `ability_overrides.yaml` on top. Matches
/// `agentrouter.registry.load_all_models` field-for-field, including the
/// "manual entries win on key collision" and staleness-aggregate-warning
/// behavior.
pub fn load_all_models(
    reg_dir: &Path,
    providers: &HashMap<String, Provider>,
) -> Result<(Vec<ModelEntry>, Vec<String>), RegistryError> {
    let (mut models, mut warnings) = load_models(&reg_dir.join("models.yaml"), providers)?;
    let mut seen: HashSet<String> = models.iter().map(|m| m.key()).collect();

    let mut generated: Vec<PathBuf> = std::fs::read_dir(reg_dir)
        .map(|entries| {
            entries
                .filter_map(|e| e.ok())
                .map(|e| e.path())
                .filter(|p| {
                    p.file_name()
                        .and_then(|n| n.to_str())
                        .map(|n| n.starts_with("models.") && n.ends_with(".generated.yaml"))
                        .unwrap_or(false)
                })
                .collect()
        })
        .unwrap_or_default();
    generated.sort();

    for gen_path in generated {
        let (gen_models, gen_warnings) = load_models(&gen_path, providers)?;
        warnings.extend(gen_warnings);
        for m in gen_models {
            let key = m.key();
            if seen.contains(&key) {
                warnings.push(format!(
                    "{}: '{}' shadowed by manual models.yaml",
                    gen_path.file_name().unwrap().to_string_lossy(),
                    key
                ));
                continue;
            }
            seen.insert(key);
            models.push(m);
        }
    }

    apply_ability_overrides(reg_dir, &mut models, &mut warnings)?;

    let stale_cutoff = chrono::Local::now().date_naive() - chrono::Duration::days(STALE_AFTER_DAYS);
    let stale: Vec<String> = models
        .iter()
        .filter(|m| {
            m.last_updated_date()
                .map(|d| d < stale_cutoff)
                .unwrap_or(false)
        })
        .map(|m| m.key())
        .collect();
    if !stale.is_empty() {
        warnings.push(format!(
            "{} model(s) have last_updated older than {} days (e.g. {}) - consider 'agentrouter providers refresh' or updating models.yaml",
            stale.len(),
            STALE_AFTER_DAYS,
            stale[0]
        ));
    }

    Ok((models, warnings))
}

fn apply_ability_overrides(
    reg_dir: &Path,
    models: &mut [ModelEntry],
    warnings: &mut Vec<String>,
) -> Result<(), RegistryError> {
    let path = reg_dir.join(OVERRIDES_FILE);
    if !path.exists() {
        return Ok(());
    }
    let data = load_yaml(&path)?;
    let overrides = data
        .get(serde_yaml::Value::String("overrides".to_string()))
        .and_then(|v| v.as_mapping())
        .ok_or_else(|| RegistryError::OverridesNotAMapping(path.clone()))?
        .clone();

    let mut by_key: HashMap<String, usize> = HashMap::new();
    for (i, m) in models.iter().enumerate() {
        by_key.insert(m.key(), i);
    }

    for (key_val, scores) in overrides {
        let key = key_val.as_str().unwrap_or_default().to_string();
        let Some(&i) = by_key.get(&key) else {
            warnings.push(format!(
                "{}: '{}' does not match any loaded model - ignored",
                OVERRIDES_FILE, key
            ));
            continue;
        };
        let current = &models[i].ability;
        let mut merged = serde_yaml::Mapping::new();
        merged.insert("coding".into(), (current.coding as i64).into());
        merged.insert("reasoning".into(), (current.reasoning as i64).into());
        merged.insert("writing".into(), (current.writing as i64).into());
        if let Some(score_map) = scores.as_mapping() {
            for (k, v) in score_map {
                merged.insert(k.clone(), v.clone());
            }
        } else if !scores.is_null() {
            return Err(RegistryError::InvalidOverride {
                path: path.clone(),
                key,
                reason: "expected a mapping of ability scores".to_string(),
            });
        }
        let ability: Ability =
            serde_yaml::from_value(serde_yaml::Value::Mapping(merged)).map_err(|e| {
                RegistryError::InvalidOverride {
                    path: path.clone(),
                    key: key.clone(),
                    reason: e.to_string(),
                }
            })?;
        models[i].ability = ability;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn write(dir: &Path, name: &str, contents: &str) -> PathBuf {
        let path = dir.join(name);
        let mut f = std::fs::File::create(&path).unwrap();
        f.write_all(contents.as_bytes()).unwrap();
        path
    }

    const PROVIDERS_YAML: &str = r#"
providers:
  - id: anthropic
    adapter: anthropic
    auth_model: api-key
"#;

    const MODEL_YAML_TEMPLATE: &str = r#"
models:
  - provider: anthropic
    model_id: claude-test
    context_window: 100000
    max_output_tokens: 4096
    pricing_tier: high
    latency_tier: medium
    ability: { coding: 8, reasoning: 8, writing: 8 }
    tool_support: [tool-use]
    vision_support: false
    deprecation_status: active
"#;

    #[test]
    fn load_providers_rejects_empty() {
        let dir = tempfile::tempdir().unwrap();
        let path = write(dir.path(), "providers.yaml", "providers: []\n");
        assert!(matches!(
            load_providers(&path),
            Err(RegistryError::NoProviders(_))
        ));
    }

    #[test]
    fn load_providers_missing_file_fails_closed() {
        let dir = tempfile::tempdir().unwrap();
        let err = load_providers(&dir.path().join("nope.yaml")).unwrap_err();
        assert!(matches!(err, RegistryError::NotFound(_)));
    }

    #[test]
    fn load_models_vendor_defaults_to_provider() {
        let dir = tempfile::tempdir().unwrap();
        let ppath = write(dir.path(), "providers.yaml", PROVIDERS_YAML);
        let providers = load_providers(&ppath).unwrap();
        let mpath = write(dir.path(), "models.yaml", MODEL_YAML_TEMPLATE);
        let (models, warnings) = load_models(&mpath, &providers).unwrap();
        assert_eq!(models.len(), 1);
        assert_eq!(models[0].vendor(), "anthropic");
        assert_eq!(models[0].key(), "anthropic/claude-test");
        assert!(warnings.is_empty());
    }

    #[test]
    fn load_models_unknown_provider_fails() {
        let dir = tempfile::tempdir().unwrap();
        let providers = HashMap::new();
        let mpath = write(dir.path(), "models.yaml", MODEL_YAML_TEMPLATE);
        let err = load_models(&mpath, &providers).unwrap_err();
        assert!(matches!(err, RegistryError::UnknownProvider { .. }));
    }

    #[test]
    fn load_models_duplicate_key_fails() {
        let dir = tempfile::tempdir().unwrap();
        let providers =
            load_providers(&write(dir.path(), "providers.yaml", PROVIDERS_YAML)).unwrap();
        let entry = MODEL_YAML_TEMPLATE
            .trim_start()
            .trim_start_matches("models:\n")
            .to_string();
        let doubled = format!("models:\n{entry}{entry}");
        let mpath = write(dir.path(), "models.yaml", &doubled);
        let err = load_models(&mpath, &providers).unwrap_err();
        assert!(matches!(err, RegistryError::DuplicateModel { .. }));
    }

    #[test]
    fn load_models_unresolved_fallback_warns_not_fails() {
        let dir = tempfile::tempdir().unwrap();
        let providers =
            load_providers(&write(dir.path(), "providers.yaml", PROVIDERS_YAML)).unwrap();
        let yaml = MODEL_YAML_TEMPLATE.replace(
            "deprecation_status: active",
            "deprecation_status: active\n    fallback: [does-not-exist]",
        );
        let mpath = write(dir.path(), "models.yaml", &yaml);
        let (models, warnings) = load_models(&mpath, &providers).unwrap();
        assert_eq!(models.len(), 1);
        assert_eq!(warnings.len(), 1);
        assert!(warnings[0].contains("does-not-exist"));
    }

    #[test]
    fn unknown_field_is_rejected() {
        let dir = tempfile::tempdir().unwrap();
        let providers =
            load_providers(&write(dir.path(), "providers.yaml", PROVIDERS_YAML)).unwrap();
        let yaml = MODEL_YAML_TEMPLATE.replace(
            "deprecation_status: active",
            "deprecation_status: active\n    bogus_field: nope",
        );
        let mpath = write(dir.path(), "models.yaml", &yaml);
        let err = load_models(&mpath, &providers).unwrap_err();
        assert!(matches!(err, RegistryError::InvalidModel { .. }));
    }

    #[test]
    fn manual_entry_wins_over_generated_on_key_collision() {
        let dir = tempfile::tempdir().unwrap();
        let providers =
            load_providers(&write(dir.path(), "providers.yaml", PROVIDERS_YAML)).unwrap();
        write(dir.path(), "models.yaml", MODEL_YAML_TEMPLATE);
        write(
            dir.path(),
            "models.anthropic.generated.yaml",
            &MODEL_YAML_TEMPLATE.replace("max_output_tokens: 4096", "max_output_tokens: 1"),
        );
        let (models, warnings) = load_all_models(dir.path(), &providers).unwrap();
        assert_eq!(models.len(), 1);
        assert_eq!(models[0].max_output_tokens, 4096);
        assert!(warnings.iter().any(|w| w.contains("shadowed")));
    }

    #[test]
    fn ability_overrides_merge_and_ignore_unknown_keys() {
        let dir = tempfile::tempdir().unwrap();
        let providers =
            load_providers(&write(dir.path(), "providers.yaml", PROVIDERS_YAML)).unwrap();
        write(dir.path(), "models.yaml", MODEL_YAML_TEMPLATE);
        write(
            dir.path(),
            "ability_overrides.yaml",
            "overrides:\n  anthropic/claude-test: { coding: 10 }\n  anthropic/missing: { coding: 1 }\n",
        );
        let (models, warnings) = load_all_models(dir.path(), &providers).unwrap();
        assert_eq!(models[0].ability.coding, 10);
        assert_eq!(models[0].ability.reasoning, 8);
        assert!(warnings.iter().any(|w| w.contains("missing")));
    }

    #[test]
    fn real_seed_registries_load_without_error() {
        let reg_dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../agentrouter/seeds");
        let providers = load_providers(&reg_dir.join("providers.yaml")).unwrap();
        let (models, _warnings) = load_all_models(&reg_dir, &providers).unwrap();
        assert!(!models.is_empty());
    }
}
