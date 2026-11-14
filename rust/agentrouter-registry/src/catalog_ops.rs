//! Offline operations for generated provider catalogs.
//! Mirrors the read-only subset of `agentrouter.catalog_ops`.

use std::collections::HashSet;
use std::io;
use std::path::{Path, PathBuf};

use chrono::NaiveDate;
use serde_yaml::Value;
use thiserror::Error;
use unicode_general_category::{get_general_category, GeneralCategory};

use crate::{read_bytes_nofollow, read_text_nofollow, STALE_AFTER_DAYS};

pub const GENERATED_GLOB: &str = "models.*.generated.yaml";

/// Typed failures corresponding to Python's public catalog-operation errors.
#[derive(Debug, Error)]
pub enum CatalogOpsError {
    #[error("invalid provider id: {provider:?}")]
    InvalidProvider { provider: String },
    #[error("invalid generated catalog provider id")]
    InvalidProviderName,
    #[error("invalid generated catalog path: {0}")]
    InvalidCatalogPath(PathBuf),
    #[error("{path}: cannot read file: {detail}")]
    ReadCatalog { path: String, detail: String },
    #[error("{path}: not valid UTF-8: {detail}")]
    InvalidUtf8 { path: String, detail: String },
    #[error("{path}: invalid YAML: {detail}")]
    InvalidYaml { path: String, detail: String },
    #[error("{path}: expected a mapping at the top level")]
    NotAMapping { path: String },
    #[error("{0} already exists — remove or roll it back before restoring the backup")]
    AlreadyExists(PathBuf),
    #[error("{0}")]
    Io(#[from] io::Error),
    #[error("cannot create backup {path}: {source}")]
    CreateBackup {
        path: PathBuf,
        #[source]
        source: io::Error,
    },
}

impl CatalogOpsError {
    /// Stable Python exception category for compatibility checks and clients.
    pub fn python_error_kind(&self) -> &'static str {
        match self {
            Self::InvalidProvider { .. } => "ValueError",
            Self::InvalidProviderName
            | Self::InvalidCatalogPath(_)
            | Self::ReadCatalog { .. }
            | Self::InvalidUtf8 { .. }
            | Self::InvalidYaml { .. }
            | Self::NotAMapping { .. } => "CatalogError",
            Self::AlreadyExists(_) => "FileExistsError",
            Self::Io(error) => io_python_error_kind(error),
            Self::CreateBackup { source, .. } => io_python_error_kind(source),
        }
    }
}

fn io_python_error_kind(error: &io::Error) -> &'static str {
    match error.kind() {
        io::ErrorKind::NotFound => "FileNotFoundError",
        io::ErrorKind::PermissionDenied => "PermissionError",
        io::ErrorKind::AlreadyExists => "FileExistsError",
        _ => "OSError",
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CatalogStatus {
    pub provider: String,
    pub path: PathBuf,
    pub count: usize,
    pub newest: Option<NaiveDate>,
    pub age_days: Option<i64>,
    pub stale: bool,
    pub source_url: Option<String>,
    pub fetched_at: Option<String>,
    pub tool_version: Option<String>,
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

fn provider_of(path: &Path) -> Result<String, CatalogOpsError> {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| CatalogOpsError::InvalidCatalogPath(path.to_path_buf()))?;
    // Python extracts this with `path.name[7:-15]`, then validates the result.
    let chars: Vec<char> = name.chars().collect();
    let provider: String = chars
        .iter()
        .skip(7)
        .take(chars.len().saturating_sub(22))
        .collect();
    if provider.is_empty()
        || !provider
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        return Err(CatalogOpsError::InvalidProviderName);
    }
    Ok(provider)
}

fn validate_provider(provider: &str) -> Result<(), CatalogOpsError> {
    if provider.is_empty()
        || !provider
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        return Err(CatalogOpsError::InvalidProvider {
            provider: provider.to_owned(),
        });
    }
    Ok(())
}

fn exists_or_symlink(path: &Path) -> bool {
    path.exists() || std::fs::symlink_metadata(path).is_ok()
}

fn rotate_backup(backup: &Path) -> Result<(), CatalogOpsError> {
    use std::time::{SystemTime, UNIX_EPOCH};

    let mut suffix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| io::Error::other(error.to_string()))?
        .as_nanos();
    loop {
        let filename = backup
            .file_name()
            .and_then(|filename| filename.to_str())
            .ok_or_else(|| CatalogOpsError::InvalidCatalogPath(backup.to_path_buf()))?;
        let rotated = backup.with_file_name(format!("{filename}.{suffix}"));
        if !exists_or_symlink(&rotated) {
            return std::fs::rename(backup, &rotated).map_err(CatalogOpsError::Io);
        }
        suffix = suffix.saturating_add(1);
    }
}

/// Back up then remove the single generated catalog for `provider`.
///
/// Backup creation is exclusive and refuses linked/non-file source paths. A
/// prior backup is moved to a unique history name before a new backup is made.
pub fn rollback(reg_dir: &Path, provider: &str) -> Result<Option<PathBuf>, CatalogOpsError> {
    validate_provider(provider)?;
    let path = reg_dir.join(format!("models.{provider}.generated.yaml"));
    if !path.exists() {
        return Ok(None);
    }
    let filename = path
        .file_name()
        .and_then(|filename| filename.to_str())
        .ok_or_else(|| CatalogOpsError::InvalidCatalogPath(path.clone()))?;
    let backup = path.with_file_name(format!("{filename}.bak"));
    if exists_or_symlink(&backup) {
        rotate_backup(&backup)?;
    }

    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut backup_file = options
        .open(&backup)
        .map_err(|error| CatalogOpsError::CreateBackup {
            path: backup.clone(),
            source: error,
        })?;
    let result = (|| {
        let contents = read_bytes_nofollow(&path)?;
        std::io::Write::write_all(&mut backup_file, &contents)?;
        drop(backup_file);
        std::fs::remove_file(&path).map_err(CatalogOpsError::Io)
    })();
    if let Err(error) = result {
        let _ = std::fs::remove_file(&backup);
        return Err(error);
    }
    Ok(Some(backup))
}

/// Restore the most recent backup, refusing to overwrite a refreshed catalog.
pub fn restore(reg_dir: &Path, provider: &str) -> Result<Option<PathBuf>, CatalogOpsError> {
    validate_provider(provider)?;
    let path = reg_dir.join(format!("models.{provider}.generated.yaml"));
    let filename = path
        .file_name()
        .and_then(|filename| filename.to_str())
        .ok_or_else(|| CatalogOpsError::InvalidCatalogPath(path.clone()))?;
    let backup = path.with_file_name(format!("{filename}.bak"));
    if !backup.exists() {
        return Ok(None);
    }
    let contents = read_bytes_nofollow(&backup)?;
    if exists_or_symlink(&path) {
        return Err(CatalogOpsError::AlreadyExists(path));
    }
    // create_new is an atomic no-clobber operation, including if another
    // process creates the destination after the existence check above.
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut restored = options.open(&path).map_err(|error| {
        if error.kind() == io::ErrorKind::AlreadyExists {
            CatalogOpsError::AlreadyExists(path.clone())
        } else {
            CatalogOpsError::Io(error)
        }
    })?;
    if let Err(error) = std::io::Write::write_all(&mut restored, &contents) {
        drop(restored);
        let _ = std::fs::remove_file(&path);
        return Err(CatalogOpsError::Io(error));
    }
    drop(restored);
    std::fs::remove_file(&backup)?;
    Ok(Some(path))
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

pub fn read_status(path: &Path, today: NaiveDate) -> Result<CatalogStatus, CatalogOpsError> {
    let provider = provider_of(path)?;
    let text = read_text_nofollow(path).map_err(|error| {
        let path = sanitize(&path.to_string_lossy());
        if error.kind() == io::ErrorKind::InvalidData {
            CatalogOpsError::InvalidUtf8 {
                path,
                detail: error.to_string(),
            }
        } else {
            CatalogOpsError::ReadCatalog {
                path,
                detail: error.to_string(),
            }
        }
    })?;
    let raw: Value = serde_yaml::from_str(&text).map_err(|error| CatalogOpsError::InvalidYaml {
        path: sanitize(&path.to_string_lossy()),
        detail: error.to_string(),
    })?;
    let raw = match raw {
        Value::Null => Value::Mapping(Default::default()),
        Value::Mapping(_) => raw,
        _ => {
            return Err(CatalogOpsError::NotAMapping {
                path: sanitize(&path.to_string_lossy()),
            })
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
    let stale = age_days.is_none_or(|days| days > STALE_AFTER_DAYS);
    let provenance = raw.get("provenance").and_then(Value::as_mapping);
    let provenance_value = |name: &str| {
        provenance
            .and_then(|mapping| mapping.get(name))
            .and_then(Value::as_str)
            .map(str::to_owned)
    };
    let source_url = provenance_value("source_url").as_deref().map(sanitize);
    Ok(CatalogStatus {
        provider,
        path: path.to_path_buf(),
        count,
        newest,
        age_days,
        stale,
        source_url,
        fetched_at: provenance_value("fetched_at"),
        tool_version: provenance_value("tool_version"),
    })
}

/// Return the provenance mapping when the file is valid; malformed or legacy
/// files are a best-effort miss, matching Python's read-only helper.
pub fn read_provenance(path: &Path) -> Option<Value> {
    let text = read_text_nofollow(path).ok()?;
    let raw: Value = serde_yaml::from_str(&text).ok()?;
    raw.get("provenance")
        .and_then(Value::as_mapping)
        .map(|mapping| Value::Mapping(mapping.clone()))
}

/// Ids removed between catalog snapshots, in stable sorted order.
pub fn deprecations(previous_ids: &HashSet<String>, current_ids: &HashSet<String>) -> Vec<String> {
    let mut removed: Vec<_> = previous_ids.difference(current_ids).cloned().collect();
    removed.sort();
    removed
}

pub fn list_generated(
    reg_dir: &Path,
    today: NaiveDate,
) -> Result<Vec<CatalogStatus>, CatalogOpsError> {
    // Path.glob returns an empty iterator when the directory does not exist or
    // is a regular file, matching that public Python helper behavior.
    if !reg_dir.is_dir() {
        return Ok(Vec::new());
    }
    let mut paths = Vec::new();
    for entry in std::fs::read_dir(reg_dir)? {
        let path = entry?.path();
        let Some(name) = path.file_name() else {
            continue;
        };
        let display = name.to_string_lossy();
        if display.starts_with("models.") && display.ends_with(".generated.yaml") {
            if name.to_str().is_none() {
                return Err(CatalogOpsError::InvalidProviderName);
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deprecations_are_sorted_and_report_only() {
        let previous = ["zeta", "removed", "alpha"]
            .into_iter()
            .map(str::to_owned)
            .collect();
        let current = ["zeta", "new"].into_iter().map(str::to_owned).collect();
        assert_eq!(deprecations(&previous, &current), ["alpha", "removed"]);
    }

    #[test]
    fn read_provenance_is_best_effort_and_mapping_only() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("models.openai.generated.yaml");
        std::fs::write(
            &path,
            "models: []\nprovenance:\n  source_url: https://example.test\n",
        )
        .unwrap();
        assert_eq!(
            read_provenance(&path),
            Some(serde_yaml::from_str("source_url: https://example.test").unwrap())
        );
        std::fs::write(&path, "provenance: [not, a, mapping]\n").unwrap();
        assert_eq!(read_provenance(&path), None);
        std::fs::write(&path, "provenance: [\n").unwrap();
        assert_eq!(read_provenance(&path), None);
    }

    #[test]
    fn status_preserves_all_provenance_fields() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("models.openai.generated.yaml");
        std::fs::write(
            &path,
            "models: []\nprovenance:\n  source_url: https://example.test\n  fetched_at: 2026-11-12T00:00:00Z\n  tool_version: 0.5.0rc1\n",
        )
        .unwrap();
        let status = read_status(&path, NaiveDate::from_ymd_opt(2026, 11, 12).unwrap()).unwrap();
        assert_eq!(status.source_url.as_deref(), Some("https://example.test"));
        assert_eq!(status.fetched_at.as_deref(), Some("2026-11-12T00:00:00Z"));
        assert_eq!(status.tool_version.as_deref(), Some("0.5.0rc1"));
    }

    #[test]
    fn rollback_and_restore_preserve_catalog_bytes() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("models.openai.generated.yaml");
        let original = b"models: [\xff, raw bytes]\n";
        std::fs::write(&path, original).unwrap();

        let backup = rollback(directory.path(), "openai").unwrap().unwrap();
        assert!(!path.exists());
        assert_eq!(std::fs::read(&backup).unwrap(), original);
        assert_eq!(
            restore(directory.path(), "openai").unwrap(),
            Some(path.clone())
        );
        assert_eq!(std::fs::read(path).unwrap(), original);
    }

    #[test]
    fn rollback_rotates_backup_and_restore_refuses_to_clobber() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("models.openai.generated.yaml");
        std::fs::write(&path, "first").unwrap();
        let backup = rollback(directory.path(), "openai").unwrap().unwrap();
        std::fs::write(&path, "second").unwrap();
        let second_backup = rollback(directory.path(), "openai").unwrap().unwrap();
        assert_eq!(std::fs::read(&backup).unwrap(), b"second");
        let rotated = directory.path().join(format!(
            "{}.",
            backup.file_name().unwrap().to_string_lossy()
        ));
        assert!(std::fs::read_dir(directory.path())
            .unwrap()
            .filter_map(Result::ok)
            .any(|entry| entry
                .file_name()
                .to_string_lossy()
                .starts_with(rotated.file_name().unwrap().to_string_lossy().as_ref())));
        assert_eq!(std::fs::read(second_backup).unwrap(), b"second");

        std::fs::write(&path, "refreshed").unwrap();
        assert!(restore(directory.path(), "openai")
            .unwrap_err()
            .to_string()
            .contains("already exists"));
    }

    #[test]
    fn catalog_file_operations_reject_unsafe_provider_ids() {
        let directory = tempfile::tempdir().unwrap();
        assert!(rollback(directory.path(), "../escape")
            .unwrap_err()
            .to_string()
            .contains("invalid provider"));
        assert!(restore(directory.path(), "../escape")
            .unwrap_err()
            .to_string()
            .contains("invalid provider"));
    }

    #[cfg(unix)]
    #[test]
    fn rollback_rotates_symlink_backup_without_touching_its_target() {
        use std::os::unix::fs::symlink;

        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("models.openai.generated.yaml");
        let backup = directory.path().join("models.openai.generated.yaml.bak");
        let outside = directory.path().join("outside.txt");
        std::fs::write(&path, "generated").unwrap();
        std::fs::write(&outside, "untouched").unwrap();
        symlink(&outside, &backup).unwrap();

        rollback(directory.path(), "openai").unwrap();
        assert_eq!(std::fs::read(&outside).unwrap(), b"untouched");
        assert_eq!(std::fs::read(&backup).unwrap(), b"generated");
        assert!(std::fs::read_dir(directory.path())
            .unwrap()
            .filter_map(Result::ok)
            .any(|entry| entry
                .file_name()
                .to_string_lossy()
                .starts_with("models.openai.generated.yaml.bak.")));
    }

    #[cfg(unix)]
    #[test]
    fn rollback_refuses_a_symlink_catalog_source() {
        use std::os::unix::fs::symlink;

        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("models.openai.generated.yaml");
        let outside = directory.path().join("outside.yaml");
        std::fs::write(&outside, "outside data").unwrap();
        symlink(&outside, &path).unwrap();

        assert!(rollback(directory.path(), "openai").is_err());
        assert_eq!(std::fs::read(&outside).unwrap(), b"outside data");
        assert!(std::fs::symlink_metadata(&path)
            .unwrap()
            .file_type()
            .is_symlink());
        assert!(!directory
            .path()
            .join("models.openai.generated.yaml.bak")
            .exists());
    }

    #[cfg(unix)]
    #[test]
    fn restore_refuses_a_symlink_generated_destination() {
        use std::os::unix::fs::symlink;

        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("models.openai.generated.yaml");
        let backup = directory.path().join("models.openai.generated.yaml.bak");
        let outside = directory.path().join("outside.yaml");
        std::fs::write(&outside, "outside data").unwrap();
        std::fs::write(&backup, "backup data").unwrap();
        symlink(&outside, &path).unwrap();

        assert!(restore(directory.path(), "openai")
            .unwrap_err()
            .to_string()
            .contains("already exists"));
        assert_eq!(std::fs::read(&outside).unwrap(), b"outside data");
        assert_eq!(std::fs::read(&backup).unwrap(), b"backup data");
    }
}
