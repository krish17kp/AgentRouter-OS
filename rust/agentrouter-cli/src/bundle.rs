//! Allowlisted, redacted Rust counterpart for `agentrouter/bundle.py`.
//!
//! The default bundle contains diagnostic state and aggregate data shape only.
//! Task text, credentials, and arbitrary files are never collected. Including
//! the SQLite decision log is an explicit opt-in.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use chrono::{SecondsFormat, Utc};
use rusqlite::{Connection, OpenFlags};
use serde_json::{json, Value};

pub const MAX_ARTIFACT_BYTES: usize = 2_000_000;

#[derive(Debug)]
pub struct BundleError(String);

impl std::fmt::Display for BundleError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.0)
    }
}

impl std::error::Error for BundleError {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Bundle {
    pub directory: PathBuf,
    pub files: Vec<String>,
}

fn existing_path(path: &Path) -> bool {
    fs::symlink_metadata(path).is_ok()
}

fn bounded(text: &str) -> String {
    let redacted = crate::observability::redact_strict(text);
    if redacted.len() <= MAX_ARTIFACT_BYTES {
        return redacted;
    }
    let suffix = "\n... truncated ...\n";
    let mut end = MAX_ARTIFACT_BYTES - suffix.len();
    while !redacted.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}{suffix}", &redacted[..end])
}

fn write_text(directory: &Path, name: &str, text: &str) -> Result<(), BundleError> {
    let content = if name.ends_with(".json") {
        let value: Value = serde_json::from_str(text)
            .map_err(|_| BundleError("bundle JSON artifact is malformed".into()))?;
        let content =
            serde_json::to_string_pretty(&crate::observability::redact_value_strict(&value))
                .map_err(|_| BundleError("bundle JSON artifact could not be serialized".into()))?;
        if content.len() > MAX_ARTIFACT_BYTES {
            return Err(BundleError(
                "bundle JSON artifact exceeds size limit".into(),
            ));
        }
        content
    } else {
        bounded(text)
    };
    // Pin the already-canonicalized destination directory and create the final
    // component through cap-std. This refuses a concurrently planted symlink or
    // Windows reparse point instead of relying on a path-based std open.
    let parent = cap_std::fs::Dir::from_std_file(
        crate::open_safe_home(directory)
            .map_err(|_| BundleError(format!("refusing to open bundle directory: {name}")))?,
    );
    let mut options = cap_std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    let file = parent.open_with(name, &options).map_err(|_| {
        BundleError(format!(
            "refusing to overwrite or follow a bundle path: {name}"
        ))
    })?;
    #[cfg(unix)]
    let mut file = {
        use std::os::unix::fs::PermissionsExt;
        let file = file.into_std();
        file.set_permissions(std::fs::Permissions::from_mode(0o600))
            .map_err(|_| BundleError(format!("could not restrict bundle artifact: {name}")))?;
        file
    };
    #[cfg(not(unix))]
    let mut file = file.into_std();
    file.write_all(content.as_bytes())
        .map_err(|_| BundleError(format!("could not write bundle artifact: {name}")))
}

fn environment_summary() -> Value {
    let settings = [
        "AGENTROUTER_HOME",
        "AGENTROUTER_API_KEY",
        "AGENTROUTER_LOG",
        "AGENTROUTER_OTEL",
        "AGENTROUTER_RATE_LIMIT",
        "AGENTROUTER_RATE_WINDOW",
        "AGENTROUTER_IDEMPOTENCY_TTL",
        "AGENTROUTER_USER",
    ];
    let values = settings
        .iter()
        .map(|name| {
            let value = match std::env::var(name) {
                Err(_) => "unset".to_owned(),
                Ok(raw) if name.ends_with("_KEY") => {
                    if raw.trim().is_empty() {
                        "set but blank".to_owned()
                    } else {
                        "set (value withheld)".to_owned()
                    }
                }
                Ok(raw) if *name == "AGENTROUTER_HOME" => fs::canonicalize(&raw)
                    .unwrap_or_else(|_| PathBuf::from(&raw))
                    .display()
                    .to_string(),
                Ok(raw) if raw.trim().is_empty() => "set but blank".to_owned(),
                Ok(_) => "set (value withheld)".to_owned(),
            };
            ((*name).to_owned(), Value::String(value))
        })
        .collect::<serde_json::Map<String, Value>>();
    Value::Object(values)
}

fn generated_at() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, false)
}

fn decision_shape(home: &Path) -> Result<Value, BundleError> {
    let db = home.join("agentrouter.db");
    if !db.exists() {
        return Ok(json!({"database": "absent"}));
    }
    let conn = Connection::open_with_flags(
        &db,
        OpenFlags::SQLITE_OPEN_READ_ONLY
            | OpenFlags::SQLITE_OPEN_NO_MUTEX
            | OpenFlags::SQLITE_OPEN_NOFOLLOW,
    )
    .map_err(|_| BundleError("decision log is unreadable".into()))?;
    let counts = (|| -> rusqlite::Result<(i64, i64, String, String)> {
        let decisions = conn.query_row("SELECT COUNT(*) FROM decisions", [], |row| row.get(0))?;
        let feedback = conn.query_row("SELECT COUNT(*) FROM feedback", [], |row| row.get(0))?;
        let journal = conn.query_row("PRAGMA journal_mode", [], |row| row.get(0))?;
        let integrity = conn.query_row("PRAGMA integrity_check", [], |row| row.get(0))?;
        Ok((decisions, feedback, journal, integrity))
    })()
    .map_err(|_| BundleError("decision log is missing required tables or is unreadable".into()))?;
    let size = fs::symlink_metadata(&db)
        .map_err(|_| BundleError("decision log size could not be read".into()))?
        .len();
    Ok(json!({
        "decisions": counts.0,
        "feedback": counts.1,
        "journal_mode": counts.2,
        "integrity": counts.3,
        "size_bytes": size,
    }))
}

#[cfg(unix)]
fn restrict_directory(directory: &Path) -> Result<(), BundleError> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(directory, fs::Permissions::from_mode(0o700))
        .map_err(|_| BundleError("bundle directory permissions could not be restricted".into()))
}

#[cfg(not(unix))]
fn restrict_directory(_directory: &Path) -> Result<(), BundleError> {
    Ok(())
}

pub fn create(
    home: &Path,
    destination: &Path,
    include_database: bool,
) -> Result<Bundle, BundleError> {
    if existing_path(destination) {
        return Err(BundleError(format!(
            "{} already exists; choose a new path rather than overwriting a bundle",
            destination.display()
        )));
    }
    let parent_path = destination.parent().unwrap_or_else(|| Path::new("."));
    let parent =
        cap_std::fs::Dir::from_std_file(crate::open_safe_home(parent_path).map_err(|_| {
            BundleError("bundle parent directory could not be created safely".into())
        })?);
    let leaf = destination
        .file_name()
        .ok_or_else(|| BundleError("bundle destination must name a directory".into()))?;
    parent
        .create_dir(leaf)
        .map_err(|_| BundleError("bundle destination could not be created safely".into()))?;
    restrict_directory(destination)?;
    let directory = fs::canonicalize(destination)
        .map_err(|_| BundleError("bundle destination could not be resolved".into()))?;
    let pinned_directory = cap_std::fs::Dir::from_std_file(
        crate::open_safe_home(&directory)
            .map_err(|_| BundleError("bundle directory could not be opened safely".into()))?,
    );
    if existing_path(&directory.join("doctor.json")) {
        return Err(BundleError("refusing to write through a symlink".into()));
    }

    let checks = crate::diagnostics::run_all(home);
    let doctor = json!({
        "generated_at": generated_at(),
        "status": crate::diagnostics::worst(&checks),
        "checks": checks,
    });
    let environment = json!({
        "agentrouter_version": agentrouter_core::package_version(),
        "rust_probe_version": env!("CARGO_PKG_VERSION"),
        "runtime": "rust",
        "platform": std::env::consts::OS,
        "settings": environment_summary(),
    });
    let shape = decision_shape(home)?;
    write_text(
        &directory,
        "doctor.json",
        &serde_json::to_string_pretty(&doctor).unwrap(),
    )?;
    write_text(
        &directory,
        "environment.json",
        &serde_json::to_string_pretty(&environment).unwrap(),
    )?;
    write_text(
        &directory,
        "data-shape.json",
        &serde_json::to_string_pretty(&shape).unwrap(),
    )?;

    let mut files = vec![
        "data-shape.json".to_owned(),
        "doctor.json".to_owned(),
        "environment.json".to_owned(),
    ];
    if include_database {
        agentrouter_storage::snapshot_into_dir(home, &pinned_directory, "decisions.db")
            .map_err(|_| BundleError("decision log snapshot could not be created".into()))?;
        files.push("decisions.db".into());
    }
    let readme = format!(
        "AgentRouter OS diagnostic bundle\n================================\n\n\
Contents are allowlisted, not collected by scanning a directory.\n\
  doctor.json      every diagnostic check and its remedy\n\
  environment.json versions and which settings are set (never their values)\n\
  data-shape.json  row counts and integrity - no task text, no prompts\n{}\n\
No .env file, credential file or API key value is ever collected.\n\
Text is passed through the same redaction the logs use.\n{}",
        if include_database {
            "  decisions.db     your decision log, INCLUDING task text you routed\n"
        } else {
            ""
        },
        if include_database {
            "\nYou opted into --include-database, so this bundle DOES contain the\ntask text you routed. Review it before sharing.\n"
        } else {
            ""
        }
    );
    write_text(&directory, "README.txt", &readme)?;
    files.push("README.txt".into());
    files.sort();
    Ok(Bundle { directory, files })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_artifacts_remain_valid_and_hide_short_and_path_shaped_secrets() {
        let directory = tempfile::tempdir().unwrap();
        let token = "ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklm/nopqrstuvwxyz.py";
        write_text(directory.path(), "doctor.json", &json!({"path": token, "APİ_KEY": "abc", "settings": {"AGENTROUTER_API_KEY": "set (value withheld)"}}).to_string()).unwrap();
        let raw = fs::read_to_string(directory.path().join("doctor.json")).unwrap();
        let value: Value = serde_json::from_str(&raw).unwrap();
        assert!(!raw.contains(token));
        assert_eq!(value["APİ_KEY"], "[redacted]");
        assert_eq!(
            value["settings"]["AGENTROUTER_API_KEY"],
            "set (value withheld)"
        );
    }

    #[test]
    fn text_is_redacted_before_utf8_truncation_and_stays_within_byte_cap() {
        let token = "ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklm/nopqrstuvwxyz.py";
        let text = format!(
            "{} {token} {}",
            "é ".repeat(MAX_ARTIFACT_BYTES / 3 - 5),
            "x ".repeat(50)
        );
        let result = bounded(&text);
        assert!(result.len() <= MAX_ARTIFACT_BYTES);
        assert!(!result.contains("ABCDEFGHIJ"));
        assert!(result.ends_with("\n... truncated ...\n"));
    }

    #[test]
    fn malformed_and_oversized_json_create_no_artifact() {
        let directory = tempfile::tempdir().unwrap();
        for text in [
            "{".to_owned(),
            json!({"text": "x ".repeat(MAX_ARTIFACT_BYTES)}).to_string(),
        ] {
            assert!(write_text(directory.path(), "doctor.json", &text).is_err());
            assert!(!directory.path().join("doctor.json").exists());
        }
    }

    #[cfg(unix)]
    #[test]
    fn bundle_artifacts_are_private_by_default() {
        use std::os::unix::fs::PermissionsExt;

        let directory = tempfile::tempdir().unwrap();
        write_text(directory.path(), "README.txt", "safe").unwrap();
        assert_eq!(
            fs::metadata(directory.path().join("README.txt"))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
    }

    #[test]
    fn generated_at_uses_python_compatible_utc_iso8601_precision() {
        let value = generated_at();
        assert!(value.ends_with("+00:00"));
        assert_eq!(value.len(), 32);
        assert_eq!(value.as_bytes().get(19), Some(&b'.'));
        assert_eq!(value.as_bytes().get(26), Some(&b'+'));
    }

    #[cfg(unix)]
    #[test]
    fn artifact_write_refuses_a_symlinked_final_path() {
        use std::os::unix::fs::symlink;

        let directory = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        let target = outside.path().join("victim.txt");
        std::fs::write(&target, "keep").unwrap();
        symlink(&target, directory.path().join("README.txt")).unwrap();

        assert!(write_text(directory.path(), "README.txt", "replace").is_err());
        assert_eq!(std::fs::read_to_string(target).unwrap(), "keep");
    }

    #[cfg(unix)]
    #[test]
    fn bundle_creation_refuses_a_symlinked_parent_directory() {
        use std::os::unix::fs::symlink;

        let root = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        let linked = root.path().join("linked");
        symlink(outside.path(), &linked).unwrap();
        let destination = linked.join("bundle");

        assert!(create(root.path(), &destination, false).is_err());
        assert!(!outside.path().join("bundle").exists());
    }

    #[test]
    fn bundle_creation_builds_missing_parent_directories_safely() {
        let root = tempfile::tempdir().unwrap();
        let destination = root.path().join("nested").join("child").join("bundle");

        let bundle = create(root.path(), &destination, false).unwrap();
        assert_eq!(
            bundle.directory,
            std::fs::canonicalize(&destination).unwrap()
        );
        assert!(bundle.directory.join("README.txt").is_file());
    }

    #[cfg(unix)]
    #[test]
    fn decision_shape_rejects_a_symlinked_database_leaf() {
        use std::os::unix::fs::symlink;

        let home = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();
        let victim = outside.path().join("victim.db");
        std::fs::write(&victim, b"not agentrouter").unwrap();
        symlink(&victim, home.path().join("agentrouter.db")).unwrap();

        assert!(decision_shape(home.path()).is_err());
        assert_eq!(std::fs::read(&victim).unwrap(), b"not agentrouter");
    }
}
