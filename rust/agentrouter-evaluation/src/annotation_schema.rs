//! Validated annotation artifact types mirrored from
//! `agentrouter.annotation.schema`.

use chrono::{DateTime, FixedOffset, NaiveDate, NaiveDateTime, SecondsFormat, Utc};
use serde::de::{self, Visitor};
use serde::{Deserialize, Serialize};
use serde::{Deserializer, Serializer};
use std::fmt;

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
    struct FloatVisitor;

    impl<'de> Visitor<'de> for FloatVisitor {
        type Value = f64;

        fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
            formatter.write_str("a float, numeric string, or boolean accepted by Pydantic")
        }

        fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
            Ok(if value { 1.0 } else { 0.0 })
        }

        fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E> {
            Ok(value as f64)
        }

        fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E> {
            Ok(value as f64)
        }

        fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E> {
            Ok(value)
        }

        fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            value.trim().parse::<f64>().map_err(E::custom)
        }
    }

    deserializer.deserialize_any(FloatVisitor)
}

fn pydantic_bool<'de, D>(deserializer: D) -> Result<bool, D::Error>
where
    D: Deserializer<'de>,
{
    struct BoolVisitor;

    impl<'de> Visitor<'de> for BoolVisitor {
        type Value = bool;

        fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
            formatter.write_str("a boolean accepted by Pydantic")
        }

        fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
            Ok(value)
        }

        fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            match value {
                0 => Ok(false),
                1 => Ok(true),
                _ => Err(E::custom("boolean integer must be 0 or 1")),
            }
        }

        fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            match value {
                0 => Ok(false),
                1 => Ok(true),
                _ => Err(E::custom("boolean integer must be 0 or 1")),
            }
        }

        fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            match value {
                0.0 => Ok(false),
                1.0 => Ok(true),
                _ => Err(E::custom("boolean number must be 0 or 1")),
            }
        }

        fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            match value.to_ascii_lowercase().as_str() {
                "0" | "off" | "false" | "no" | "n" | "f" => Ok(false),
                "1" | "on" | "true" | "yes" | "y" | "t" => Ok(true),
                _ => Err(E::custom("invalid boolean string")),
            }
        }
    }

    deserializer.deserialize_any(BoolVisitor)
}

fn pydantic_u32<'de, D>(deserializer: D) -> Result<u32, D::Error>
where
    D: Deserializer<'de>,
{
    struct IntegerVisitor;

    impl<'de> Visitor<'de> for IntegerVisitor {
        type Value = u32;

        fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
            formatter.write_str("an integer accepted by Pydantic")
        }

        fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
            Ok(u32::from(value))
        }

        fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            u32::try_from(value).map_err(E::custom)
        }

        fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            u32::try_from(value).map_err(E::custom)
        }

        fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            if value.is_finite() && value.fract() == 0.0 && (0.0..=u32::MAX as f64).contains(&value)
            {
                Ok(value as u32)
            } else {
                Err(E::custom("value must be an unsigned 32-bit integer"))
            }
        }

        fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
        where
            E: de::Error,
        {
            value.trim().parse::<u32>().map_err(E::custom)
        }
    }

    deserializer.deserialize_any(IntegerVisitor)
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
                deserializer.deserialize_any(self)
            }

            fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
            where
                E: de::Error,
            {
                if let Ok(timestamp) = value.parse::<f64>() {
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
        let whole = seconds.floor();
        let nanos = ((seconds - whole) * 1_000_000_000.0).round() as u32;
        let timestamp = DateTime::<Utc>::from_timestamp(whole as i64, nanos)
            .ok_or_else(|| "datetime timestamp is out of range".to_owned())?;
        Ok(format_aware(timestamp.fixed_offset()))
    }

    fn normalize_iso(value: &str) -> Result<String, String> {
        if let Ok(parsed) = DateTime::<FixedOffset>::parse_from_rfc3339(value) {
            return Ok(format_aware(parsed));
        }
        // Python fromisoformat accepts a space separator and date-only input.
        let iso = value.replace(' ', "T");
        if let Ok(parsed) = NaiveDateTime::parse_from_str(&iso, "%Y-%m-%dT%H:%M:%S%.f") {
            return Ok(format_naive(parsed));
        }
        if let Ok(parsed) = NaiveDate::parse_from_str(value, "%Y-%m-%d") {
            return Ok(format_naive(
                parsed.and_hms_opt(0, 0, 0).expect("valid midnight"),
            ));
        }
        Err(format!("invalid datetime {value:?}"))
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
    #[serde(deserialize_with = "pydantic_u32")]
    pub schema_version: u32,
    #[serde(default = "default_manifest_dataset")]
    pub dataset: String,
    pub version: String,
    pub created: String,
    #[serde(default)]
    pub split_counts: std::collections::BTreeMap<String, u64>,
    #[serde(default)]
    pub split_sha256: std::collections::BTreeMap<String, String>,
    #[serde(default)]
    pub category_counts: std::collections::BTreeMap<String, u64>,
    #[serde(default)]
    pub band_counts: std::collections::BTreeMap<String, u64>,
    #[serde(default = "default_true")]
    #[serde(deserialize_with = "pydantic_bool")]
    pub frozen_holdout_untouched: bool,
    #[serde(default)]
    pub leakage_report: Option<String>,
    #[serde(default)]
    pub provenance: String,
}

fn default_schema_version() -> u32 {
    SCHEMA_VERSION
}

fn default_true() -> bool {
    true
}
