//! Allowlisted, redacted Rust counterpart for `agentrouter/bundle.py`.
//!
//! The default bundle contains diagnostic state and aggregate data shape only.
//! Task text, credentials, and arbitrary files are never collected. Including
//! the SQLite decision log is an explicit opt-in.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use chrono::Utc;
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
    let redacted = crate::observability::redact(text);
    if redacted.len() <= MAX_ARTIFACT_BYTES {
        return redacted;
    }
    let mut end = MAX_ARTIFACT_BYTES;
    while !redacted.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}\n... truncated ...\n", &redacted[..end])
}

fn write_text(directory: &Path, name: &str, text: &str) -> Result<(), BundleError> {
    let path = directory.join(name);
    let content = bounded(text);
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&path)
        .map_err(|_| {
            BundleError(format!(
                "refusing to overwrite or follow a bundle path: {name}"
            ))
        })?;
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

fn decision_shape(home: &Path) -> Result<Value, BundleError> {
    let db = home.join("agentrouter.db");
    if !db.exists() {
        return Ok(json!({"database": "absent"}));
    }
    let conn = Connection::open_with_flags(
        &db,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
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
    let size = fs::metadata(&db)
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

#[cfg(unix)]
fn restrict_file(path: &Path) -> Result<(), BundleError> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(path, fs::Permissions::from_mode(0o600))
        .map_err(|_| BundleError("decision snapshot permissions could not be restricted".into()))
}

#[cfg(not(unix))]
fn restrict_file(_path: &Path) -> Result<(), BundleError> {
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
    if let Some(parent) = destination.parent() {
        fs::create_dir_all(parent)
            .map_err(|_| BundleError("bundle parent directory could not be created".into()))?;
    }
    fs::create_dir(destination)
        .map_err(|_| BundleError("bundle destination could not be created safely".into()))?;
    restrict_directory(destination)?;
    let directory = fs::canonicalize(destination)
        .map_err(|_| BundleError("bundle destination could not be resolved".into()))?;
    if existing_path(&directory.join("doctor.json")) {
        return Err(BundleError("refusing to write through a symlink".into()));
    }

    let checks = crate::diagnostics::run_all(home);
    let doctor = json!({
        "generated_at": Utc::now().to_rfc3339(),
        "status": crate::diagnostics::worst(&checks),
        "checks": checks,
    });
    let environment = json!({
        "rust_probe_version": env!("CARGO_PKG_VERSION"),
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
        let snapshot = directory.join("decisions.db");
        OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&snapshot)
            .map_err(|_| BundleError("decision snapshot destination already exists".into()))?;
        restrict_file(&snapshot)?;
        agentrouter_storage::snapshot(home, &snapshot)
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
