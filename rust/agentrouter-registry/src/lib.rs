//! Rust port of `agentrouter/registry.py` + the registry-entry models from
//! `agentrouter/schema.py`. Field names, YAML shapes, and error conditions
//! mirror the Python module exactly — this is the contract the Python/Rust
//! compatibility test in `tests/` checks against the real seed registries.

use std::collections::{HashMap, HashSet};
use std::io::Read;
use std::path::{Path, PathBuf};

use chrono::{Datelike, NaiveDate, NaiveTime};
use serde::{Deserialize, Serialize};
use thiserror::Error;

pub use agentrouter_core::PricingTier;
pub mod catalog_ops;
pub mod refresh;

pub const STALE_AFTER_DAYS: i64 = 90;
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
    #[serde(deserialize_with = "deserialize_pydantic_ability_score")]
    pub coding: u8,
    #[serde(deserialize_with = "deserialize_pydantic_ability_score")]
    pub reasoning: u8,
    #[serde(deserialize_with = "deserialize_pydantic_ability_score")]
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
    #[serde(
        default = "default_true",
        deserialize_with = "deserialize_pydantic_bool"
    )]
    pub supports_noninteractive: bool,
    #[serde(default, deserialize_with = "deserialize_pydantic_bool")]
    pub supports_file_edit: bool,
    #[serde(default, deserialize_with = "deserialize_pydantic_bool")]
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
#[derive(Debug, Clone, Serialize, Deserialize)]
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
    #[serde(deserialize_with = "deserialize_positive_pydantic_integer")]
    pub context_window: serde_json::Number,
    #[serde(
        default,
        deserialize_with = "deserialize_optional_positive_pydantic_integer"
    )]
    pub max_input_tokens: Option<serde_json::Number>,
    #[serde(deserialize_with = "deserialize_positive_pydantic_integer")]
    pub max_output_tokens: serde_json::Number,
    pub pricing_tier: PricingTier,
    pub latency_tier: LatencyTier,
    #[serde(default, deserialize_with = "deserialize_optional_pydantic_f64")]
    pub input_price_per_million: Option<f64>,
    #[serde(default, deserialize_with = "deserialize_optional_pydantic_f64")]
    pub output_price_per_million: Option<f64>,
    pub pricing_basis: Option<String>,
    #[serde(default, deserialize_with = "deserialize_pydantic_date")]
    pub pricing_effective_date: Option<String>,
    pub ability: Ability,
    #[serde(default = "default_ability_source")]
    pub ability_source: AbilitySource,
    #[serde(default, deserialize_with = "deserialize_optional_pydantic_f64")]
    pub ability_confidence: Option<f64>,
    pub tool_support: Vec<String>,
    #[serde(deserialize_with = "deserialize_pydantic_bool")]
    pub vision_support: bool,
    #[serde(default, deserialize_with = "deserialize_pydantic_bool")]
    pub audio_support: bool,
    #[serde(default, deserialize_with = "deserialize_pydantic_bool")]
    pub video_support: bool,
    #[serde(default, deserialize_with = "deserialize_pydantic_bool")]
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
    /// Normalized ISO `YYYY-MM-DD` string. Deserialization mirrors Pydantic's
    /// `date | None` input forms while keeping the registry JSON contract
    /// stable; [`ModelEntry::last_updated_date`] parses it for staleness checks.
    #[serde(default, deserialize_with = "deserialize_pydantic_date")]
    pub last_updated: Option<String>,
    #[serde(default, deserialize_with = "deserialize_pydantic_date")]
    pub last_verified: Option<String>,
}

/// Pydantic's `date | None` accepts ISO dates, midnight ISO datetimes, and
/// epoch values that resolve to UTC midnight. Keep the normalized value as an
/// ISO date string so the registry's public JSON shape remains unchanged.
fn deserialize_pydantic_date<'de, D>(deserializer: D) -> Result<Option<String>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    struct OptionalDateVisitor;

    impl<'de> serde::de::Visitor<'de> for OptionalDateVisitor {
        type Value = Option<String>;

        fn expecting(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            formatter.write_str("a date, a midnight datetime, an epoch value, or null")
        }

        fn visit_none<E>(self) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            Ok(None)
        }

        fn visit_unit<E>(self) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            Ok(None)
        }

        fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
        where
            D: serde::Deserializer<'de>,
        {
            deserializer.deserialize_any(DateValueVisitor).map(Some)
        }
    }

    struct DateValueVisitor;

    impl<'de> serde::de::Visitor<'de> for DateValueVisitor {
        type Value = String;

        fn expecting(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            formatter.write_str("a valid Pydantic date value")
        }

        fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            parse_pydantic_date(value).ok_or_else(|| E::custom("invalid date value"))
        }

        fn visit_string<E>(self, value: String) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            self.visit_str(&value)
        }

        fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            epoch_date(value as f64).ok_or_else(|| E::custom("invalid date value"))
        }

        fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            epoch_date(value as f64).ok_or_else(|| E::custom("invalid date value"))
        }

        fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
        where
            E: serde::de::Error,
        {
            epoch_date(value).ok_or_else(|| E::custom("invalid date value"))
        }
    }

    deserializer.deserialize_option(OptionalDateVisitor)
}

fn parse_pydantic_date(value: &str) -> Option<String> {
    if let Ok(date) = NaiveDate::parse_from_str(value, "%Y-%m-%d") {
        return Some(date.format("%Y-%m-%d").to_string());
    }
    if let Ok(epoch) = value.parse::<f64>() {
        return epoch_date(epoch);
    }

    let date_text = value.get(..10)?;
    let date = NaiveDate::parse_from_str(date_text, "%Y-%m-%d").ok()?;
    let separator = value.as_bytes().get(10).copied()?;
    if !matches!(separator, b'T' | b't' | b' ' | b'_') {
        return None;
    }
    let tail = value.get(11..)?;
    let (time_text, zone) = split_datetime_zone(tail)?;
    if let Some(zone) = zone {
        validate_datetime_zone(zone)?;
    }

    let time_text = time_text.replace(',', ".");
    let normalized_time = match time_text.matches(':').count() {
        1 => format!("{time_text}:00"),
        2 => time_text,
        _ => return None,
    };
    let time = chrono::NaiveTime::parse_from_str(&normalized_time, "%H:%M:%S%.f").ok()?;
    if time != NaiveTime::MIN {
        return None;
    }
    Some(date.format("%Y-%m-%d").to_string())
}

fn split_datetime_zone(value: &str) -> Option<(&str, Option<&str>)> {
    if let Some(time) = value.strip_suffix(['Z', 'z']) {
        return Some((time, Some("Z")));
    }
    if let Some((index, _)) = value
        .char_indices()
        .skip(1)
        .find(|(_, character)| matches!(character, '+' | '-'))
    {
        let (time, zone) = value.split_at(index);
        return Some((time, Some(zone)));
    }
    Some((value, None))
}

fn validate_datetime_zone(zone: &str) -> Option<()> {
    if zone == "Z" {
        return Some(());
    }
    let sign = match zone.as_bytes().first()? {
        b'+' => 1_i32,
        b'-' => -1_i32,
        _ => return None,
    };
    let suffix = &zone[1..];
    let digits = match suffix.len() {
        4 => suffix.to_owned(),
        5 if suffix.as_bytes().get(2) == Some(&b':') => {
            format!("{}{}", &suffix[..2], &suffix[3..])
        }
        _ => return None,
    };
    if digits.len() != 4 || !digits.bytes().all(|byte| byte.is_ascii_digit()) {
        return None;
    }
    let hours: i32 = digits[..2].parse().ok()?;
    let minutes: i32 = digits[2..].parse().ok()?;
    if hours > 23 || minutes > 59 {
        return None;
    }
    chrono::FixedOffset::east_opt(sign * (hours * 3600 + minutes * 60)).map(|_| ())
}

fn epoch_date(value: f64) -> Option<String> {
    if !value.is_finite() {
        return None;
    }
    let seconds = if value.abs() > 20_000_000_000.0 {
        value / 1_000.0
    } else {
        value
    };
    if seconds.fract() != 0.0 {
        return None;
    }
    let timestamp = seconds as i64;
    let date = chrono::DateTime::from_timestamp(timestamp, 0)?.date_naive();
    if !(1..=9999).contains(&date.year()) {
        return None;
    }
    Some(date.format("%Y-%m-%d").to_string())
}

#[derive(Debug)]
enum PydanticScalar {
    Bool(bool),
    Signed(i64),
    Unsigned(u64),
    Float(f64),
    JsonNumber(String),
    Text(String),
}

struct PydanticScalarVisitor;

impl<'de> serde::de::Visitor<'de> for PydanticScalarVisitor {
    type Value = PydanticScalar;

    fn expecting(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("a Pydantic-compatible scalar")
    }

    fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Bool(value))
    }

    fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Signed(value))
    }

    fn visit_i128<E>(self, value: i128) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        i64::try_from(value)
            .map(PydanticScalar::Signed)
            .or_else(|_| Ok(PydanticScalar::JsonNumber(value.to_string())))
    }

    fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Unsigned(value))
    }

    fn visit_u128<E>(self, value: u128) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        u64::try_from(value)
            .map(PydanticScalar::Unsigned)
            .or_else(|_| Ok(PydanticScalar::JsonNumber(value.to_string())))
    }

    fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Float(value))
    }

    fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Text(value.to_owned()))
    }

    fn visit_string<E>(self, value: String) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        Ok(PydanticScalar::Text(value))
    }

    fn visit_map<M>(self, mut map: M) -> Result<Self::Value, M::Error>
    where
        M: serde::de::MapAccess<'de>,
    {
        // serde_json's arbitrary_precision feature presents JSON numbers to
        // custom visitors as a one-entry map with this private key. Decode
        // only that exact representation; ordinary YAML/JSON mappings remain
        // invalid scalar values.
        let key = map.next_key::<String>()?;
        if key.as_deref() != Some("$serde_json::private::Number") {
            return Err(serde::de::Error::custom("expected a scalar value"));
        }
        let number = map.next_value::<String>()?;
        if map.next_key::<serde::de::IgnoredAny>()?.is_some() {
            return Err(serde::de::Error::custom("expected one scalar value"));
        }
        Ok(parse_json_number_text(number))
    }
}

impl<'de> Deserialize<'de> for PydanticScalar {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        deserializer.deserialize_any(PydanticScalarVisitor)
    }
}

fn parse_json_number_text(value: String) -> PydanticScalar {
    if is_integer_number_text(&value) {
        PydanticScalar::JsonNumber(value)
    } else {
        value
            .parse::<f64>()
            .map(PydanticScalar::Float)
            .unwrap_or(PydanticScalar::JsonNumber(value))
    }
}

fn is_integer_number_text(value: &str) -> bool {
    let digits = value.strip_prefix('-').unwrap_or(value);
    !digits.is_empty() && digits.bytes().all(|byte| byte.is_ascii_digit())
}

fn strip_valid_digit_separators(value: &str) -> Option<String> {
    let characters: Vec<char> = value.chars().collect();
    let mut normalized = String::with_capacity(value.len());
    for (index, character) in characters.iter().copied().enumerate() {
        if character == '_' {
            if !characters
                .get(index.wrapping_sub(1))
                .is_some_and(|previous| previous.is_ascii_digit())
                || !characters
                    .get(index + 1)
                    .is_some_and(|next| next.is_ascii_digit())
            {
                return None;
            }
        } else {
            normalized.push(character);
        }
    }
    Some(normalized)
}

fn parse_bounded_integer_text(value: &str, max: u64) -> Option<u64> {
    let normalized = strip_valid_digit_separators(value.trim())?;
    let (negative, unsigned) = match normalized.as_bytes().first()? {
        b'-' => (true, &normalized[1..]),
        b'+' => (false, &normalized[1..]),
        _ => (false, normalized.as_str()),
    };
    let (integer, fraction) = match unsigned.split_once('.') {
        Some((integer, fraction)) => {
            if integer.is_empty()
                || fraction.is_empty()
                || unsigned.matches('.').count() != 1
                || !fraction.bytes().all(|byte| byte == b'0')
            {
                return None;
            }
            (integer, Some(fraction))
        }
        None => (unsigned, None),
    };
    if integer.is_empty() || !integer.bytes().all(|byte| byte.is_ascii_digit()) {
        return None;
    }
    if fraction.is_some_and(|digits| !digits.bytes().all(|byte| byte.is_ascii_digit())) {
        return None;
    }
    let mut parsed = 0_u64;
    for digit in integer.bytes() {
        parsed = parsed
            .checked_mul(10)?
            .checked_add(u64::from(digit - b'0'))?;
        if parsed > max {
            return None;
        }
    }
    if negative && parsed != 0 {
        return None;
    }
    Some(parsed)
}

fn parse_pydantic_integer(value: PydanticScalar, max: u64) -> Option<u64> {
    match value {
        PydanticScalar::Bool(value) => Some(u64::from(value)),
        PydanticScalar::Signed(value) => u64::try_from(value).ok().filter(|value| *value <= max),
        PydanticScalar::Unsigned(value) => (value <= max).then_some(value),
        PydanticScalar::Float(value) => {
            (value.is_finite() && value.fract() == 0.0 && value >= 0.0 && value <= max as f64)
                .then_some(value as u64)
        }
        PydanticScalar::JsonNumber(value) => {
            if is_integer_number_text(&value) {
                parse_bounded_integer_text(&value, max)
            } else {
                let value = value.parse::<f64>().ok()?;
                (value.is_finite() && value.fract() == 0.0 && value >= 0.0 && value <= max as f64)
                    .then_some(value as u64)
            }
        }
        PydanticScalar::Text(value) => parse_bounded_integer_text(&value, max),
    }
}

fn parse_pydantic_float(value: PydanticScalar) -> Option<f64> {
    match value {
        PydanticScalar::Bool(value) => Some(f64::from(u8::from(value))),
        PydanticScalar::Signed(value) => Some(value as f64),
        PydanticScalar::Unsigned(value) => Some(value as f64),
        PydanticScalar::Float(value) => Some(value),
        PydanticScalar::JsonNumber(value) => value.parse::<f64>().ok(),
        PydanticScalar::Text(value) => {
            let normalized = if value.contains('_') {
                strip_valid_digit_separators(&value)?
            } else {
                value.trim().to_owned()
            };
            normalized.parse::<f64>().ok()
        }
    }
}

fn parse_pydantic_bool(value: PydanticScalar) -> Option<bool> {
    match value {
        PydanticScalar::Bool(value) => Some(value),
        PydanticScalar::Signed(0) | PydanticScalar::Unsigned(0) => Some(false),
        PydanticScalar::Signed(1) | PydanticScalar::Unsigned(1) => Some(true),
        PydanticScalar::Float(0.0) => Some(false),
        PydanticScalar::Float(1.0) => Some(true),
        PydanticScalar::JsonNumber(value) => match value.parse::<f64>().ok()? {
            0.0 => Some(false),
            1.0 => Some(true),
            _ => None,
        },
        // Pydantic's bool validator accepts case-insensitive tokens but does
        // not trim strings (unlike its int and float validators).
        PydanticScalar::Text(value) => match value.to_ascii_lowercase().as_str() {
            "0" | "false" | "off" | "no" | "n" | "f" => Some(false),
            "1" | "true" | "on" | "yes" | "y" | "t" => Some(true),
            _ => None,
        },
        _ => None,
    }
}

fn deserialize_pydantic_ability_score<'de, D>(deserializer: D) -> Result<u8, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = PydanticScalar::deserialize(deserializer)?;
    parse_pydantic_integer(value, 10)
        .and_then(|value| u8::try_from(value).ok())
        .ok_or_else(|| serde::de::Error::custom("ability score must be an integer from 0 to 10"))
}

fn pydantic_integer(value: PydanticScalar) -> Option<serde_json::Number> {
    let value = match value {
        PydanticScalar::Bool(value) => serde_json::Value::Bool(value),
        PydanticScalar::Signed(value) => serde_json::Value::Number(value.into()),
        PydanticScalar::Unsigned(value) => serde_json::Value::Number(value.into()),
        PydanticScalar::Float(value) => {
            serde_json::Value::Number(serde_json::Number::from_f64(value)?)
        }
        PydanticScalar::JsonNumber(value) => serde_json::Value::Number(value.parse().ok()?),
        PydanticScalar::Text(value) => serde_json::Value::String(value),
    };
    agentrouter_core::pydantic_integer_from_value(&value).ok()
}

fn deserialize_positive_pydantic_integer<'de, D>(
    deserializer: D,
) -> Result<serde_json::Number, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = pydantic_integer(PydanticScalar::deserialize(deserializer)?)
        .filter(agentrouter_core::pydantic_integer_is_positive)
        .ok_or_else(|| serde::de::Error::custom("value must be a positive integer"))?;
    Ok(value)
}

fn deserialize_optional_positive_pydantic_integer<'de, D>(
    deserializer: D,
) -> Result<Option<serde_json::Number>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    Option::<PydanticScalar>::deserialize(deserializer)?
        .map(|value| {
            pydantic_integer(value)
                .filter(agentrouter_core::pydantic_integer_is_positive)
                .ok_or_else(|| serde::de::Error::custom("value must be a positive integer"))
        })
        .transpose()
}

fn deserialize_pydantic_bool<'de, D>(deserializer: D) -> Result<bool, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = PydanticScalar::deserialize(deserializer)?;
    parse_pydantic_bool(value).ok_or_else(|| serde::de::Error::custom("invalid boolean value"))
}

fn deserialize_optional_pydantic_f64<'de, D>(deserializer: D) -> Result<Option<f64>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    Option::<PydanticScalar>::deserialize(deserializer)?
        .map(|value| {
            parse_pydantic_float(value)
                .ok_or_else(|| serde::de::Error::custom("invalid float value"))
        })
        .transpose()
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
    /// Enforce the Pydantic `Field` constraints from `schema.ModelEntry`.
    /// Serde's primitive types alone allow zero sizes and non-finite floats.
    fn validate(&self) -> Result<(), String> {
        if !agentrouter_core::pydantic_integer_is_positive(&self.context_window) {
            return Err("context_window must be greater than 0".to_string());
        }
        if self
            .max_input_tokens
            .as_ref()
            .is_some_and(|value| !agentrouter_core::pydantic_integer_is_positive(value))
        {
            return Err("max_input_tokens must be greater than 0".to_string());
        }
        if !agentrouter_core::pydantic_integer_is_positive(&self.max_output_tokens) {
            return Err("max_output_tokens must be greater than 0".to_string());
        }
        for (name, score) in [
            ("ability.coding", self.ability.coding),
            ("ability.reasoning", self.ability.reasoning),
            ("ability.writing", self.ability.writing),
        ] {
            if score > 10 {
                return Err(format!("{name} must be at most 10"));
            }
        }
        for (name, price) in [
            ("input_price_per_million", self.input_price_per_million),
            ("output_price_per_million", self.output_price_per_million),
        ] {
            if price.is_some_and(|value| !value.is_finite() || value < 0.0) {
                return Err(format!("{name} must be finite and non-negative"));
            }
        }
        if self
            .ability_confidence
            .is_some_and(|value| !value.is_finite() || !(0.0..=1.0).contains(&value))
        {
            return Err("ability_confidence must be finite and between 0 and 1".to_string());
        }
        for (name, date) in [
            (
                "pricing_effective_date",
                self.pricing_effective_date.as_ref(),
            ),
            ("last_updated", self.last_updated.as_ref()),
            ("last_verified", self.last_verified.as_ref()),
        ] {
            if date.is_some_and(|value| NaiveDate::parse_from_str(value, "%Y-%m-%d").is_err()) {
                return Err(format!("{name} must be an ISO date"));
            }
        }
        Ok(())
    }

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
    #[serde(default, deserialize_with = "deserialize_pydantic_bool")]
    pub supports_execution: bool,
    #[serde(default)]
    pub exec_command: Vec<String>,
}

fn default_auth_model() -> String {
    "none".to_string()
}

pub(crate) fn read_text_nofollow(path: &Path) -> std::io::Result<String> {
    let bytes = read_bytes_nofollow(path)?;
    String::from_utf8(bytes)
        .map_err(|error| std::io::Error::new(std::io::ErrorKind::InvalidData, error))
}

pub(crate) fn read_bytes_nofollow(path: &Path) -> std::io::Result<Vec<u8>> {
    let metadata = std::fs::symlink_metadata(path)?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "linked or non-file registry path",
        ));
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if metadata.file_attributes() & 0x400 != 0 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "linked registry path",
            ));
        }
    }
    let mut options = std::fs::OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK);
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        options.custom_flags(0x0020_0000); // FILE_FLAG_OPEN_REPARSE_POINT
    }
    let mut file = options.open(path)?;
    let opened = file.metadata()?;
    if !opened.is_file() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "linked or non-file registry path",
        ));
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if opened.file_attributes() & 0x400 != 0 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "linked registry path",
            ));
        }
    }
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)?;
    Ok(bytes)
}

fn load_yaml(path: &Path) -> Result<serde_yaml::Mapping, RegistryError> {
    if !path.exists() {
        return Err(RegistryError::NotFound(path.to_path_buf()));
    }
    let text = read_text_nofollow(path)
        .map_err(|e| RegistryError::InvalidYaml(path.to_path_buf(), e.to_string()))?;
    let normalized = quote_unbounded_model_token_integers(&text);
    let value: serde_yaml::Value = serde_yaml::from_str(&normalized)
        .map_err(|e| RegistryError::InvalidYaml(path.to_path_buf(), e.to_string()))?;
    if contains_json_number_marker(&value) {
        return Err(RegistryError::InvalidYaml(
            path.to_path_buf(),
            "reserved serde_json numeric marker is not valid YAML registry data".to_string(),
        ));
    }
    value
        .as_mapping()
        .cloned()
        .ok_or_else(|| RegistryError::NotAMapping(path.to_path_buf()))
}

/// serde_yaml's value representation rejects integers outside i64/u64 before
/// Pydantic-compatible field coercion can see them. Quote only oversized
/// integer scalars assigned to the three unbounded token-count fields; their
/// custom deserializers then parse the decimal strings exactly.
fn quote_unbounded_model_token_integers(text: &str) -> String {
    const KEYS: [&str; 3] = ["context_window", "max_input_tokens", "max_output_tokens"];

    let mut result = String::with_capacity(text.len());
    let mut block_parent_indent = None;
    let mut block_content_indent = None;
    let mut quote = None;
    for line in text.split_inclusive('\n') {
        let content = line.strip_suffix('\n').unwrap_or(line);
        let indent = content.bytes().take_while(|byte| *byte == b' ').count();
        let nonblank = content[indent..].trim().is_empty();
        if let Some(parent_indent) = block_parent_indent {
            if nonblank {
                result.push_str(line);
                continue;
            }
            match block_content_indent {
                Some(content_indent) if indent >= content_indent => {
                    result.push_str(line);
                    continue;
                }
                None if indent > parent_indent => {
                    block_content_indent = Some(indent);
                    result.push_str(line);
                    continue;
                }
                _ => {
                    block_parent_indent = None;
                    block_content_indent = None;
                }
            }
        }

        let bytes = content.as_bytes();
        let mut output = Vec::with_capacity(content.len() + 16);
        let mut index = 0;
        while index < bytes.len() {
            let byte = bytes[index];
            if let Some(delimiter) = quote {
                output.push(byte);
                if delimiter == b'"' && byte == b'\\' {
                    index += 1;
                    if let Some(escaped) = bytes.get(index) {
                        output.push(*escaped);
                    }
                } else if byte == delimiter {
                    if delimiter == b'\'' && bytes.get(index + 1) == Some(&b'\'') {
                        index += 1;
                        output.push(b'\'');
                    } else {
                        quote = None;
                    }
                }
                index += 1;
                continue;
            }
            if byte == b'"' || byte == b'\'' {
                quote = Some(byte);
                output.push(byte);
                index += 1;
                continue;
            }
            if byte == b'#' && (index == 0 || bytes[index - 1].is_ascii_whitespace()) {
                output.extend_from_slice(&bytes[index..]);
                break;
            }

            let matched = KEYS.iter().find(|key| {
                let key_bytes = key.as_bytes();
                let end = index + key_bytes.len();
                bytes.get(index..end) == Some(key_bytes)
                    && bytes.get(end) == Some(&b':')
                    && (index == 0
                        || bytes[index - 1].is_ascii_whitespace()
                        || matches!(bytes[index - 1], b'{' | b',' | b'-'))
            });
            if let Some(key) = matched {
                let mut value_start = index + key.len() + 1;
                while bytes
                    .get(value_start)
                    .is_some_and(|byte| matches!(byte, b' ' | b'\t'))
                {
                    value_start += 1;
                }
                let mut value_end = value_start;
                if bytes
                    .get(value_end)
                    .is_some_and(|byte| matches!(byte, b'+' | b'-'))
                {
                    value_end += 1;
                }
                while bytes
                    .get(value_end)
                    .is_some_and(|byte| byte.is_ascii_digit() || *byte == b'_')
                {
                    value_end += 1;
                }
                let token = &content[value_start..value_end];
                let normalized = token.replace('_', "");
                let digits = normalized
                    .strip_prefix('-')
                    .or_else(|| normalized.strip_prefix('+'))
                    .unwrap_or(&normalized);
                let valid_integer = strip_valid_digit_separators(token).is_some()
                    && !digits.is_empty()
                    && digits.bytes().all(|byte| byte.is_ascii_digit());
                let delimiter = bytes.get(value_end);
                let scalar_ends_here = delimiter.is_none_or(|byte| {
                    byte.is_ascii_whitespace() || matches!(byte, b',' | b'}' | b']' | b'#')
                });
                let fits = normalized.parse::<i64>().is_ok() || normalized.parse::<u64>().is_ok();
                if valid_integer && scalar_ends_here && !fits {
                    output.extend_from_slice(&bytes[index..value_start]);
                    output.push(b'"');
                    output.extend_from_slice(token.as_bytes());
                    output.push(b'"');
                    index = value_end;
                    continue;
                }
            }

            output.push(byte);
            index += 1;
        }
        result.push_str(&String::from_utf8(output).expect("copied YAML UTF-8 remains valid"));

        let trimmed = content.trim_end();
        let without_comment = trimmed
            .split_once(" #")
            .map_or(trimmed, |(prefix, _)| prefix)
            .trim_end();
        let has_scalar_marker = without_comment.rsplit_once(':').is_some_and(|(_, value)| {
            matches!(value.trim(), "|" | ">" | "|-" | ">-" | "|+" | ">+")
        });
        if quote.is_none() && has_scalar_marker {
            block_parent_indent = Some(indent);
            block_content_indent = None;
        }
        if line.ends_with('\n') {
            result.push('\n');
        }
    }
    result
}

#[cfg(test)]
mod unbounded_yaml_tests {
    use super::quote_unbounded_model_token_integers;

    #[test]
    fn oversized_token_integers_are_quoted_only_as_yaml_scalars() {
        let huge = "1267650600228229401496703205376";
        let source = format!(
            "models:\n  - context_window: {huge}\n    max_input_tokens: -{huge}\n    extra: {{max_output_tokens: {huge}}}\n    notes: |\n      context_window: {huge}\n    label: \"context_window: {huge} — 🧭\"\n    # max_output_tokens: {huge}\n"
        );
        let rewritten = quote_unbounded_model_token_integers(&source);
        assert!(rewritten.contains(&format!("context_window: \"{huge}\"")));
        assert!(rewritten.contains(&format!("max_input_tokens: \"-{huge}\"")));
        assert!(rewritten.contains(&format!("max_output_tokens: \"{huge}\"}}")));
        assert!(rewritten.contains(&format!("      context_window: {huge}")));
        assert!(rewritten.contains(&format!("label: \"context_window: {huge} — 🧭\"")));
        assert!(rewritten.contains(&format!("# max_output_tokens: {huge}")));
    }
}

fn contains_json_number_marker(value: &serde_yaml::Value) -> bool {
    match value {
        serde_yaml::Value::Sequence(values) => values.iter().any(contains_json_number_marker),
        serde_yaml::Value::Mapping(values) => values.iter().any(|(key, value)| {
            key == "$serde_json::private::Number" || contains_json_number_marker(value)
        }),
        serde_yaml::Value::Tagged(value) => contains_json_number_marker(value.value()),
        _ => false,
    }
}

fn seq_field(map: &serde_yaml::Mapping, key: &str) -> Vec<serde_yaml::Value> {
    map.get(key)
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
            .and_then(|m| m.get("model_id"))
            .and_then(|v| v.as_str())
            .unwrap_or("<unknown>")
            .to_string();
        let m: ModelEntry =
            serde_yaml::from_value(raw).map_err(|e| RegistryError::InvalidModel {
                path: path.to_path_buf(),
                model: fallback_id.clone(),
                reason: e.to_string(),
            })?;
        m.validate().map_err(|reason| RegistryError::InvalidModel {
            path: path.to_path_buf(),
            model: fallback_id,
            reason,
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
        .get("overrides")
        .and_then(|v| v.as_mapping())
        .ok_or_else(|| RegistryError::OverridesNotAMapping(path.clone()))?
        .clone();

    let mut by_key: HashMap<String, usize> = HashMap::new();
    for (i, m) in models.iter().enumerate() {
        by_key.insert(m.key(), i);
    }

    for (key_val, scores) in overrides {
        let key = key_val.clone();
        let Some(&i) = by_key.get(&key) else {
            warnings.push(format!(
                "{}: '{}' does not match any loaded model - ignored",
                OVERRIDES_FILE, key
            ));
            continue;
        };
        let current = &models[i].ability;
        let mut merged = serde_yaml::Mapping::new();
        merged.insert("coding", (current.coding as i64).into());
        merged.insert("reasoning", (current.reasoning as i64).into());
        merged.insert("writing", (current.writing as i64).into());
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
    fn json_stream_deserializes_pydantic_float_fields() {
        let scalar: PydanticScalar = serde_json::from_str("0.4").unwrap();
        assert!(matches!(scalar, PydanticScalar::Float(value) if value == 0.4));
        let yaml = MODEL_YAML_TEMPLATE.replace(
            "deprecation_status: active",
            "deprecation_status: active\n    ability_confidence: 0.4\n    input_price_per_million: 0.125",
        );
        let document: serde_yaml::Value = serde_yaml::from_str(&yaml).unwrap();
        let model: ModelEntry = serde_yaml::from_value(document["models"][0].clone()).unwrap();
        let json = serde_json::to_string(&model).unwrap();
        let roundtrip: ModelEntry = serde_json::from_str(&json).unwrap();
        assert_eq!(roundtrip.ability_confidence, Some(0.4));
        assert_eq!(roundtrip.input_price_per_million, Some(0.125));
    }

    #[test]
    fn yaml_registry_rejects_serde_json_private_number_maps() {
        let dir = tempfile::tempdir().unwrap();
        let providers =
            load_providers(&write(dir.path(), "providers.yaml", PROVIDERS_YAML)).unwrap();
        let yaml = MODEL_YAML_TEMPLATE.replace(
            "deprecation_status: active",
            "deprecation_status: active\n    ability_confidence: { '$serde_json::private::Number': '0.4' }",
        );
        let path = write(dir.path(), "models.yaml", &yaml);
        assert!(matches!(
            load_models(&path, &providers),
            Err(RegistryError::InvalidYaml(_, _))
        ));
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
    fn schema_constraints_reject_zero_and_non_finite_values() {
        let dir = tempfile::tempdir().unwrap();
        let providers =
            load_providers(&write(dir.path(), "providers.yaml", PROVIDERS_YAML)).unwrap();
        for (old, new) in [
            ("context_window: 100000", "context_window: 0"),
            ("max_output_tokens: 4096", "max_output_tokens: 0"),
            ("coding: 8", "coding: 11"),
            (
                "pricing_tier: high",
                "pricing_tier: high\n    input_price_per_million: -.inf",
            ),
            (
                "pricing_tier: high",
                "pricing_tier: high\n    ability_confidence: .nan",
            ),
        ] {
            let path = write(
                dir.path(),
                "models.yaml",
                &MODEL_YAML_TEMPLATE.replace(old, new),
            );
            assert!(matches!(
                load_models(&path, &providers),
                Err(RegistryError::InvalidModel { .. })
            ));
        }
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
        assert_eq!(models[0].max_output_tokens.to_string(), "4096");
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
        let json = serde_json::to_vec(&models).unwrap();
        let roundtrip: Vec<ModelEntry> = serde_json::from_slice(&json).unwrap();
        assert_eq!(roundtrip.len(), models.len());
    }
}
