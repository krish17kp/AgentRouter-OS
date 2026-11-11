//! Offline freshness reports for generated provider catalogs.
//! Mirrors `agentrouter.catalog_ops.read_status` and `list_generated`.

use std::path::{Path, PathBuf};

use chrono::NaiveDate;
use serde_yaml::Value;
use unicode_general_category::{get_general_category, GeneralCategory};

use crate::{read_text_nofollow, STALE_AFTER_DAYS};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CatalogStatus {
    pub provider: String,
    pub path: PathBuf,
    pub count: usize,
    pub newest: Option<NaiveDate>,
    pub age_days: Option<i64>,
    pub stale: bool,
    pub source_url: Option<String>,
}

impl CatalogStatus {
    pub fn summary(&self) -> String {
        let when = self
            .newest
            .map(|date| date.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "unknown".to_string());
        let age = self
            .age_days
            .map(|days| format!("{days}d"))
            .unwrap_or_else(|| "unknown".to_string());
        let flag = if self.stale { "STALE" } else { "fresh" };
        let mut line = format!(
            "{:<12} {:>4} models  newest {} ({})  {}",
            self.provider, self.count, when, age, flag
        );
        if let Some(source_url) = &self.source_url {
            if !source_url.is_empty() {
                line.push_str("  source=");
                line.push_str(source_url);
            }
        }
        line
    }
}

fn sanitize(value: &str) -> String {
    value
        .chars()
        .map(|c| {
            if c == ' '
                || !matches!(
                    get_general_category(c),
                    GeneralCategory::Control
                        | GeneralCategory::Format
                        | GeneralCategory::LineSeparator
                        | GeneralCategory::ParagraphSeparator
                        | GeneralCategory::PrivateUse
                        | GeneralCategory::SpaceSeparator
                        | GeneralCategory::Surrogate
                        | GeneralCategory::Unassigned
                )
            {
                c
            } else {
                '?'
            }
        })
        .take(120)
        .collect()
}

fn provider_of(path: &Path) -> Result<String, String> {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| format!("invalid generated catalog path: {}", path.display()))?;
    let provider = name
        .strip_prefix("models.")
        .and_then(|name| name.strip_suffix(".generated.yaml"))
        .ok_or_else(|| "invalid generated catalog name".to_string())?;
    if provider.is_empty()
        || !provider
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        return Err("invalid generated catalog provider id".to_string());
    }
    Ok(provider.to_string())
}

fn parse_iso_date(value: &str) -> Option<NaiveDate> {
    let bytes = value.as_bytes();
    let digits = |slice: &[u8]| slice.iter().all(u8::is_ascii_digit);
    if bytes.len() == 10
        && bytes[4] == b'-'
        && bytes[7] == b'-'
        && digits(&bytes[..4])
        && digits(&bytes[5..7])
        && digits(&bytes[8..])
    {
        NaiveDate::parse_from_str(value, "%Y-%m-%d").ok()
    } else if bytes.len() == 8 && digits(bytes) {
        NaiveDate::parse_from_str(value, "%Y%m%d").ok()
    } else if bytes.len() == 10
        && bytes[4] == b'-'
        && bytes[5] == b'W'
        && bytes[8] == b'-'
        && digits(&bytes[..4])
        && digits(&bytes[6..8])
        && (b'1'..=b'7').contains(&bytes[9])
    {
        NaiveDate::parse_from_str(value, "%G-W%V-%u").ok()
    } else if bytes.len() == 8
        && bytes[4] == b'W'
        && digits(&bytes[..4])
        && digits(&bytes[5..7])
        && (b'1'..=b'7').contains(&bytes[7])
    {
        NaiveDate::parse_from_str(value, "%GW%V%u").ok()
    } else if bytes.len() == 8
        && bytes[4] == b'-'
        && bytes[5] == b'W'
        && digits(&bytes[..4])
        && digits(&bytes[6..])
    {
        NaiveDate::parse_from_str(&format!("{value}-1"), "%G-W%V-%u").ok()
    } else if bytes.len() == 7 && bytes[4] == b'W' && digits(&bytes[..4]) && digits(&bytes[5..]) {
        NaiveDate::parse_from_str(&format!("{value}1"), "%GW%V%u").ok()
    } else {
        None
    }
}

pub fn read_status(path: &Path, today: NaiveDate) -> Result<CatalogStatus, String> {
    let provider = provider_of(path)?;
    let text = read_text_nofollow(path).map_err(|error| {
        format!(
            "{}: cannot read file: {error}",
            sanitize(&path.to_string_lossy())
        )
    })?;
    let raw: Value = serde_yaml::from_str(&text).map_err(|error| {
        format!(
            "{}: invalid YAML: {error}",
            sanitize(&path.to_string_lossy())
        )
    })?;
    let raw = match raw {
        Value::Null => Value::Mapping(Default::default()),
        Value::Mapping(_) => raw,
        _ => {
            return Err(format!(
                "{}: expected a mapping at the top level",
                sanitize(&path.to_string_lossy())
            ))
        }
    };
    let models = raw.get("models").and_then(Value::as_sequence);
    let count = models.map_or(0, Vec::len);
    let newest = models
        .into_iter()
        .flatten()
        .filter_map(|model| model.get("last_updated"))
        .filter_map(Value::as_str)
        .filter_map(parse_iso_date)
        .max();
    let age_days = newest.map(|date| today.signed_duration_since(date).num_days());
    let stale = age_days.map_or(true, |days| days > STALE_AFTER_DAYS);
    let source_url = raw
        .get("provenance")
        .and_then(|value| value.get("source_url"))
        .and_then(Value::as_str)
        .map(sanitize);
    Ok(CatalogStatus {
        provider,
        path: path.to_path_buf(),
        count,
        newest,
        age_days,
        stale,
        source_url,
    })
}

pub fn list_generated(reg_dir: &Path, today: NaiveDate) -> Result<Vec<CatalogStatus>, String> {
    let mut paths = Vec::new();
    for entry in std::fs::read_dir(reg_dir).map_err(|error| error.to_string())? {
        let path = entry.map_err(|error| error.to_string())?.path();
        let Some(name) = path.file_name() else {
            continue;
        };
        let display = name.to_string_lossy();
        if display.starts_with("models.") && display.ends_with(".generated.yaml") {
            if name.to_str().is_none() {
                return Err("invalid generated catalog provider id".to_string());
            }
            paths.push(path);
        }
    }
    paths.sort();
    paths
        .into_iter()
        .map(|path| read_status(&path, today))
        .collect()
}
