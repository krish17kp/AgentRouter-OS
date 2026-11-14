//! Validated annotation artifact types mirrored from
//! `agentrouter.annotation.schema`.

use chrono::{DateTime, FixedOffset, NaiveDate, NaiveDateTime, SecondsFormat, Utc};
use serde::de;
use serde::{Deserialize, Serialize};
use serde::{Deserializer, Serializer};

use agentrouter_core::ContextBand;

pub const SCHEMA_VERSION: u32 = 1;
pub const CATEGORIES: [&str; 10] = [
    "coding",
    "review",
    "refactor",
    "documentation",
    "summarization",
    "analysis",
    "data-pipeline",
    "rag",
    "tool-use",
    "ambiguous",
];
pub const SPLITS: [&str; 3] = ["train", "dev", "holdout"];
pub const LABEL_SOURCES: [&str; 3] = ["generated_candidate", "curated", "real_prompt"];

fn pydantic_float<'de, D>(deserializer: D) -> Result<f64, D::Error>
where
    D: Deserializer<'de>,
{
    let value = serde_json::Value::deserialize(deserializer)?;
    match value {
        serde_json::Value::Bool(value) => Ok(if value { 1.0 } else { 0.0 }),
        serde_json::Value::Number(value) => value
            .as_f64()
            .ok_or_else(|| de::Error::custom("value must be a finite number")),
        serde_json::Value::String(value) => value.trim().parse::<f64>().map_err(de::Error::custom),
        _ => Err(de::Error::custom(
            "expected a float, numeric string, or boolean accepted by Pydantic",
        )),
    }
}

fn pydantic_bool<'de, D>(deserializer: D) -> Result<bool, D::Error>
where
    D: Deserializer<'de>,
{
    let value = serde_json::Value::deserialize(deserializer)?;
    match value {
        serde_json::Value::Bool(value) => Ok(value),
        serde_json::Value::Number(value) => match value.as_f64() {
            Some(0.0) => Ok(false),
            Some(1.0) => Ok(true),
            _ => Err(de::Error::custom("boolean number must be 0 or 1")),
        },
        serde_json::Value::String(value) => match value.to_ascii_lowercase().as_str() {
            "0" | "off" | "false" | "no" | "n" | "f" => Ok(false),
            "1" | "on" | "true" | "yes" | "y" | "t" => Ok(true),
            _ => Err(de::Error::custom("invalid boolean string")),
        },
        _ => Err(de::Error::custom(
            "value must be a boolean accepted by Pydantic",
        )),
    }
}

fn pydantic_integer<'de, D>(deserializer: D) -> Result<serde_json::Number, D::Error>
where
    D: Deserializer<'de>,
{
    let value = serde_json::Value::deserialize(deserializer)?;
    match value {
        serde_json::Value::Bool(value) => Ok(serde_json::Number::from(u8::from(value))),
        serde_json::Value::Number(value) => {
            integer_from_json_number(value).map_err(de::Error::custom)
        }
        serde_json::Value::String(value) => parse_pydantic_integer(&value)
            .and_then(number_from_integer_text)
            .map_err(de::Error::custom),
        _ => Err(de::Error::custom("value must be an integer")),
    }
}

fn integer_from_json_number(value: serde_json::Number) -> Result<serde_json::Number, String> {
    let text = value.to_string();
    if let Ok(integer) = canonical_integer_text(&text) {
        return number_from_integer_text(integer);
    }
    let value = text
        .parse::<f64>()
        .map_err(|_| "value must be an integer".to_owned())?;
    if value.is_finite()
        && value.fract() == 0.0
        && value >= i64::MIN as f64
        && value < -(i64::MIN as f64)
    {
        return Ok(serde_json::Number::from(value as i64));
    }
    Err("value must be an integer".to_owned())
}

fn parse_pydantic_integer(value: &str) -> Result<String, String> {
    let value = value.trim();
    if let Ok(normalized) = normalize_python_digits(value) {
        return canonical_integer_text(&normalized);
    }

    // Pydantic accepts underscore-separated digits and decimal strings only
    // when every fractional digit is zero (for example, "1_000", "1.0",
    // and "-0.00"). Exponent notation and fractional values are rejected.
    let (whole, fraction) = value
        .split_once('.')
        .ok_or_else(|| "value must be an integer".to_owned())?;
    if fraction.contains('.') {
        return Err("value must be an integer".to_owned());
    }
    if fraction.starts_with(['+', '-']) {
        return Err("value must be an integer".to_owned());
    }
    let whole = normalize_python_digits(whole)?;
    let fraction = normalize_python_digits(fraction)?;
    if fraction.is_empty() || fraction.bytes().any(|digit| digit != b'0') {
        return Err("value must be an integer".to_owned());
    }
    canonical_integer_text(&whole)
}

fn canonical_integer_text(value: &str) -> Result<String, String> {
    let (negative, digits) = match value.strip_prefix('-') {
        Some(digits) => (true, digits),
        None => (false, value.strip_prefix('+').unwrap_or(value)),
    };
    if digits.is_empty() || !digits.bytes().all(|byte| byte.is_ascii_digit()) {
        return Err("value must be an integer".to_owned());
    }
    let digits = digits.trim_start_matches('0');
    if digits.is_empty() {
        return Ok("0".to_owned());
    }
    Ok(if negative {
        format!("-{digits}")
    } else {
        digits.to_owned()
    })
}

fn number_from_integer_text(value: String) -> Result<serde_json::Number, String> {
    value
        .parse::<serde_json::Number>()
        .map_err(|_| "value must be an integer".to_owned())
}

fn normalize_python_digits(value: &str) -> Result<String, String> {
    let (sign, digits) = match value.strip_prefix('-') {
        Some(digits) => ("-", digits),
        None => match value.strip_prefix('+') {
            Some(digits) => ("+", digits),
            None => ("", value),
        },
    };
    let bytes = digits.as_bytes();
    if bytes.is_empty()
        || !bytes.iter().enumerate().all(|(index, byte)| {
            byte.is_ascii_digit()
                || (*byte == b'_'
                    && index > 0
                    && index + 1 < bytes.len()
                    && bytes[index - 1].is_ascii_digit()
                    && bytes[index + 1].is_ascii_digit())
        })
    {
        return Err("value must be an integer".to_owned());
    }
    Ok(format!("{sign}{}", digits.replace('_', "")))
}

#[derive(Debug)]
struct PythonInteger(serde_json::Number);

impl<'de> Deserialize<'de> for PythonInteger {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        pydantic_integer(deserializer).map(Self)
    }
}

fn pydantic_integer_map<'de, D>(
    deserializer: D,
) -> Result<std::collections::BTreeMap<String, serde_json::Number>, D::Error>
where
    D: Deserializer<'de>,
{
    let parsed = std::collections::BTreeMap::<String, PythonInteger>::deserialize(deserializer)?;
    Ok(parsed
        .into_iter()
        .map(|(key, value)| (key, value.0))
        .collect())
}

fn default_candidate_source() -> String {
    "generated_candidate".to_owned()
}

fn default_pending_review() -> String {
    "pending_human_review".to_owned()
}

fn default_manifest_dataset() -> String {
    "agentrouter-context-band-v2".to_owned()
}

fn is_empty(value: &str) -> bool {
    value.chars().count() == 0
}

fn validate_category(category: &str) -> Result<(), String> {
    if CATEGORIES.contains(&category) {
        Ok(())
    } else {
        Err(format!("unknown category {category:?}"))
    }
}

fn validate_label_source(source: &str) -> Result<(), String> {
    if LABEL_SOURCES.contains(&source) {
        Ok(())
    } else {
        Err(format!("unknown source {source:?}"))
    }
}

/// Match Pydantic's `datetime | None` JSON contract: ISO strings (including
/// naive dates/times), numeric Unix seconds/milliseconds, and numeric strings
/// are accepted; serialized values use Python's ISO form and microsecond
/// precision.
mod optional_datetime {
    use super::*;
    use serde::de::{self, Visitor};
    use std::fmt;

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Option<String>, D::Error>
    where
        D: Deserializer<'de>,
    {
        struct DateTimeVisitor;

        impl<'de> Visitor<'de> for DateTimeVisitor {
            type Value = Option<String>;

            fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                formatter.write_str("an ISO datetime, Unix timestamp, or null")
            }

            fn visit_none<E>(self) -> Result<Self::Value, E> {
                Ok(None)
            }

            fn visit_unit<E>(self) -> Result<Self::Value, E> {
                Ok(None)
            }

            fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
            where
                D: Deserializer<'de>,
            {
                match serde_json::Value::deserialize(deserializer)? {
                    serde_json::Value::Number(value) => {
                        let timestamp = value.as_f64().ok_or_else(|| {
                            de::Error::custom("datetime timestamp must be numeric")
                        })?;
                        normalize_timestamp(timestamp)
                            .map(Some)
                            .map_err(de::Error::custom)
                    }
                    serde_json::Value::String(value) => self.visit_str(&value),
                    _ => Err(de::Error::custom(
                        "an ISO datetime, Unix timestamp, or null",
                    )),
                }
            }

            fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                // Pydantic accepts signed integer and decimal timestamp
                // strings, but rejects integer-only exponent notation and
                // surrounding whitespace.
                let numeric = if value.contains('.') {
                    value.parse::<f64>().ok()
                } else {
                    let digits = value
                        .strip_prefix('-')
                        .or_else(|| value.strip_prefix('+'))
                        .unwrap_or(value)
                        .as_bytes();
                    (!digits.is_empty() && digits.iter().all(u8::is_ascii_digit))
                        .then(|| value.parse::<f64>().ok())
                        .flatten()
                };
                if let Some(timestamp) = numeric {
                    return normalize_timestamp(timestamp).map(Some).map_err(E::custom);
                }
                normalize_iso(value).map(Some).map_err(E::custom)
            }

            fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                normalize_timestamp(value as f64)
                    .map(Some)
                    .map_err(E::custom)
            }

            fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                normalize_timestamp(value as f64)
                    .map(Some)
                    .map_err(E::custom)
            }

            fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                normalize_timestamp(value).map(Some).map_err(E::custom)
            }
        }

        deserializer.deserialize_option(DateTimeVisitor)
    }

    pub fn serialize<S>(value: &Option<String>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        value.serialize(serializer)
    }

    fn normalize_timestamp(timestamp: f64) -> Result<String, String> {
        if !timestamp.is_finite() {
            return Err("datetime timestamp must be finite".to_owned());
        }
        // Pydantic interprets magnitudes above 2e10 as milliseconds.
        let seconds = if timestamp.abs() > 20_000_000_000.0 {
            timestamp / 1000.0
        } else {
            timestamp
        };
        let mut whole = seconds.floor();
        let mut micros = ((seconds - whole) * 1_000_000.0).round_ties_even() as i64;
        if micros == 1_000_000 {
            whole += 1.0;
            micros = 0;
        }
        let timestamp = DateTime::<Utc>::from_timestamp(whole as i64, micros as u32 * 1_000)
            .ok_or_else(|| "datetime timestamp is out of range".to_owned())?;
        Ok(format_aware(timestamp.fixed_offset()))
    }

    fn normalize_iso(value: &str) -> Result<String, String> {
        reject_leap_second(value, value)?;
        if let Ok(parsed) = DateTime::<FixedOffset>::parse_from_rfc3339(value) {
            return Ok(format_aware(parsed));
        }
        // Match the extended forms accepted by Pydantic's datetime parser:
        // lowercase/space/underscore separators, omitted seconds, and comma fractions.
        let mut iso = value.to_owned();
        if !iso.starts_with(char::is_numeric) && iso.len() > 10 {
            return Err(format!("invalid datetime {value:?}"));
        }
        if iso.as_bytes().get(4) != Some(&b'-') {
            return Err(format!("invalid datetime {value:?}"));
        }
        if iso.len() > 10 {
            let separator = iso.as_bytes()[10];
            if !matches!(separator, b'T' | b't' | b' ' | b'_') {
                return Err(format!("invalid datetime {value:?}"));
            }
            iso.replace_range(10..11, "T");
        }
        iso = iso.replace(',', ".");

        // chrono accepts at most nanoseconds; Python truncates longer
        // fractional-second input to its six-digit microsecond precision.
        if let Some(dot) = iso.find('.') {
            let tail = &iso[dot + 1..];
            let digits = tail.bytes().take_while(u8::is_ascii_digit).count();
            if digits > 9 {
                iso.replace_range(dot + 10..dot + digits + 1, "");
            }
        }
        if let Some(t_pos) = iso.find('T') {
            let time_start = t_pos + 1;
            let zone_pos = iso[time_start..]
                .find(['+', '-'])
                .map(|pos| pos + time_start)
                .unwrap_or(iso.len());
            let time = &iso[time_start..zone_pos];
            if time.matches(':').count() == 1 {
                iso.insert_str(zone_pos, ":00");
            }
        }
        // Pydantic accepts compact numeric UTC offsets (+HHMM).
        if let Some(time_start) = iso.find('T').map(|position| position + 1) {
            if let Some(zone_pos) = iso[time_start..]
                .rfind(['+', '-'])
                .map(|position| position + time_start)
            {
                let zone = &iso[zone_pos + 1..];
                if zone.len() == 4 && zone.bytes().all(|byte| byte.is_ascii_digit()) {
                    iso.insert(zone_pos + 3, ':');
                } else if zone.matches(':').count() > 1 {
                    return Err(format!("invalid datetime {value:?}"));
                }
            }
        }
        reject_leap_second(&iso, value)?;
        if let Ok(parsed) = DateTime::<FixedOffset>::parse_from_rfc3339(&iso) {
            return Ok(format_aware(parsed));
        }
        if let Ok(parsed) = NaiveDateTime::parse_from_str(&iso, "%Y-%m-%dT%H:%M:%S%.f") {
            return Ok(format_naive(parsed));
        }
        if let Ok(parsed) = NaiveDate::parse_from_str(&iso, "%Y-%m-%d") {
            return Ok(format_naive(
                parsed.and_hms_opt(0, 0, 0).expect("valid midnight"),
            ));
        }
        Err(format!("invalid datetime {value:?}"))
    }

    fn reject_leap_second(value: &str, original: &str) -> Result<(), String> {
        let Some(time_start) = value.find('T').map(|position| position + 1) else {
            return Ok(());
        };
        let time = &value[time_start..];
        let bytes = time.as_bytes();
        if bytes.get(2) == Some(&b':') && bytes.get(5) == Some(&b':') {
            let seconds = time.get(6..8).and_then(|digits| digits.parse::<u8>().ok());
            if matches!(seconds, Some(60..)) {
                return Err(format!("invalid datetime {original:?}"));
            }
        }
        Ok(())
    }

    fn format_naive(value: NaiveDateTime) -> String {
        if value.and_utc().timestamp_subsec_micros() == 0 {
            value.format("%Y-%m-%dT%H:%M:%S").to_string()
        } else {
            value.format("%Y-%m-%dT%H:%M:%S%.6f").to_string()
        }
    }

    fn format_aware<Tz: chrono::TimeZone>(value: DateTime<Tz>) -> String
    where
        Tz::Offset: std::fmt::Display,
    {
        let micros = value.timestamp_subsec_micros();
        let mut output = if micros == 0 {
            value.to_rfc3339_opts(SecondsFormat::Secs, false)
        } else {
            value.to_rfc3339_opts(SecondsFormat::Micros, false)
        };
        if output.ends_with("+00:00") {
            output.truncate(output.len() - 6);
            output.push('Z');
        }
        output
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Candidate {
    pub id: String,
    pub prompt: String,
    pub category: String,
    #[serde(default = "default_candidate_source")]
    pub source: String,
    #[serde(default)]
    pub template: Option<String>,
    #[serde(default)]
    pub notes: Option<String>,
}

impl Candidate {
    pub fn validate(&self) -> Result<(), String> {
        if is_empty(&self.prompt) {
            return Err("prompt must contain at least one character".to_owned());
        }
        validate_category(&self.category)?;
        validate_label_source(&self.source)
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AnnotatorLabel {
    pub annotator: String,
    #[serde(default)]
    pub band: Option<ContextBand>,
    #[serde(default)]
    #[serde(deserialize_with = "pydantic_bool")]
    pub abstain: bool,
    pub rationale: String,
    #[serde(deserialize_with = "pydantic_float")]
    pub confidence: f64,
    #[serde(
        default,
        deserialize_with = "optional_datetime::deserialize",
        serialize_with = "optional_datetime::serialize"
    )]
    pub at: Option<String>,
}

impl AnnotatorLabel {
    pub fn validate(&self) -> Result<(), String> {
        if is_empty(&self.annotator) {
            return Err("annotator must contain at least one character".to_owned());
        }
        if is_empty(&self.rationale) {
            return Err("rationale must contain at least one character".to_owned());
        }
        if !(0.0..=1.0).contains(&self.confidence) {
            return Err("confidence must be between 0 and 1".to_owned());
        }
        if self.abstain && self.band.is_some() {
            return Err("an abstained label must not carry a band".to_owned());
        }
        if !self.abstain && self.band.is_none() {
            return Err("a non-abstained label must carry a band".to_owned());
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ItemLabels {
    pub candidate_id: String,
    pub prompt: String,
    pub category: String,
    #[serde(default)]
    pub labels: Vec<AnnotatorLabel>,
}

impl ItemLabels {
    pub fn validate(&self) -> Result<(), String> {
        for label in &self.labels {
            label.validate()?;
        }
        Ok(())
    }

    pub fn annotators(&self) -> Vec<String> {
        self.labels
            .iter()
            .map(|label| label.annotator.clone())
            .collect()
    }

    pub fn agrees(&self) -> bool {
        let mut bands = self
            .labels
            .iter()
            .filter(|label| !label.abstain)
            .filter_map(|label| label.band);
        let Some(first) = bands.next() else {
            return false;
        };
        let count = 1 + bands.clone().count();
        count >= 2 && bands.all(|band| band == first)
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AdjudicatedItem {
    pub id: String,
    pub prompt: String,
    pub category: String,
    #[serde(default)]
    pub band: Option<ContextBand>,
    #[serde(default)]
    #[serde(deserialize_with = "pydantic_bool")]
    pub abstained: bool,
    pub label_source: String,
    #[serde(default)]
    pub annotators: Vec<String>,
    #[serde(default)]
    pub adjudicated_by: Option<String>,
    pub rationale: String,
    #[serde(deserialize_with = "pydantic_float")]
    pub confidence: f64,
    #[serde(default)]
    pub split: Option<String>,
    #[serde(default = "default_pending_review")]
    pub review_status: String,
}

impl AdjudicatedItem {
    pub fn validate(&self) -> Result<(), String> {
        if is_empty(&self.prompt) {
            return Err("prompt must contain at least one character".to_owned());
        }
        validate_category(&self.category)?;
        validate_label_source(&self.label_source)?;
        if self
            .split
            .as_deref()
            .is_some_and(|split| !SPLITS.contains(&split))
        {
            return Err(format!(
                "unknown split {:?}",
                self.split.as_deref().unwrap()
            ));
        }
        if self.abstained && self.band.is_some() {
            return Err("an abstained item must not carry a band".to_owned());
        }
        if !self.abstained && self.band.is_none() {
            return Err("a banded item must carry a band".to_owned());
        }
        if is_empty(&self.rationale) {
            return Err("rationale must contain at least one character".to_owned());
        }
        if !(0.0..=1.0).contains(&self.confidence) {
            return Err("confidence must be between 0 and 1".to_owned());
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct DatasetManifest {
    #[serde(default = "default_schema_version")]
    #[serde(deserialize_with = "pydantic_integer")]
    pub schema_version: serde_json::Number,
    #[serde(default = "default_manifest_dataset")]
    pub dataset: String,
    pub version: String,
    pub created: String,
    #[serde(default)]
    #[serde(deserialize_with = "pydantic_integer_map")]
    pub split_counts: std::collections::BTreeMap<String, serde_json::Number>,
    #[serde(default)]
    pub split_sha256: std::collections::BTreeMap<String, String>,
    #[serde(default)]
    #[serde(deserialize_with = "pydantic_integer_map")]
    pub category_counts: std::collections::BTreeMap<String, serde_json::Number>,
    #[serde(default, deserialize_with = "pydantic_integer_map")]
    pub band_counts: std::collections::BTreeMap<String, serde_json::Number>,
    #[serde(default = "default_true")]
    #[serde(deserialize_with = "pydantic_bool")]
    pub frozen_holdout_untouched: bool,
    #[serde(default)]
    pub leakage_report: Option<String>,
    #[serde(default)]
    pub provenance: String,
}

fn default_schema_version() -> serde_json::Number {
    serde_json::Number::from(SCHEMA_VERSION)
}

fn default_true() -> bool {
    true
}
