//! Rust diagnostics probe for the structured `agentrouter doctor` contract.
//!
//! Checks are isolated and return data rather than printing or propagating
//! errors. Plugin diagnosis and the optional HTTP extra are still Python-only;
//! this probe reports those gaps as warnings instead of pretending they passed.

use std::path::Path;

use chrono::Local;
use rusqlite::{Connection, OpenFlags};
use serde::Serialize;

pub const OK: &str = "ok";
pub const WARN: &str = "warn";
pub const FAIL: &str = "fail";

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Check {
    pub id: String,
    pub status: String,
    pub summary: String,
    pub remedy: Option<String>,
}

impl Check {
    fn new(id: &str, status: &str, summary: impl Into<String>, remedy: Option<String>) -> Self {
        Self {
            id: id.to_owned(),
            status: status.to_owned(),
            summary: summary.into(),
            remedy,
        }
    }
}

fn safe(id: &str, check: impl FnOnce() -> Check) -> Check {
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(check)).unwrap_or_else(|_| {
        Check::new(
            id,
            FAIL,
            "check failed to run (panic)",
            Some("this is a bug in the diagnostic itself; run with --json and report it".into()),
        )
    })
}

fn truthy(value: Option<String>) -> bool {
    matches!(
        value
            .unwrap_or_default()
            .trim()
            .to_ascii_lowercase()
            .as_str(),
        "1" | "true" | "yes" | "on"
    )
}

fn check_home(home: &Path) -> Check {
    if !home.exists() {
        return Check::new(
            "data.home",
            FAIL,
            format!("{} does not exist", home.display()),
            Some("run: agentrouter init".into()),
        );
    }
    match std::fs::metadata(home) {
        Ok(metadata) if !metadata.permissions().readonly() => Check::new(
            "data.home",
            OK,
            format!("{} exists and is writable", home.display()),
            None,
        ),
        Ok(_) => Check::new(
            "data.home",
            FAIL,
            format!("{} is not writable", home.display()),
            Some("check that the data directory is writable".into()),
        ),
        Err(_) => Check::new(
            "data.home",
            FAIL,
            "data directory metadata could not be read",
            Some("check the directory path and permissions".into()),
        ),
    }
}

fn check_database(home: &Path) -> Check {
    let db = home.join("agentrouter.db");
    if !db.exists() {
        return Check::new(
            "data.database",
            WARN,
            "no decision log yet",
            Some("run: agentrouter init".into()),
        );
    }
    let result = (|| -> rusqlite::Result<(i64, String, String)> {
        let conn = Connection::open_with_flags(
            db,
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )?;
        let decisions = conn.query_row("SELECT COUNT(*) FROM decisions", [], |row| row.get(0))?;
        let mode = conn.query_row("PRAGMA journal_mode", [], |row| row.get(0))?;
        let integrity = conn.query_row("PRAGMA integrity_check", [], |row| row.get(0))?;
        Ok((decisions, mode, integrity))
    })();
    match result {
        Ok((_, _, integrity)) if integrity != "ok" => Check::new(
            "data.database",
            FAIL,
            format!("integrity check reported: {integrity}"),
            Some("restore a backup or move the database aside and run: agentrouter init".into()),
        ),
        Ok((decisions, mode, _)) if !mode.eq_ignore_ascii_case("wal") => Check::new(
            "data.database",
            WARN,
            format!("{decisions} decision(s), journal_mode={mode}"),
            Some("WAL is expected; a non-WAL journal degrades under concurrent writes".into()),
        ),
        Ok((decisions, _, _)) => Check::new(
            "data.database",
            OK,
            format!("{decisions} decision(s), WAL, integrity ok"),
            None,
        ),
        Err(_) => Check::new(
            "data.database",
            FAIL,
            "decision log is missing required tables or is unreadable",
            Some(
                "restore a valid backup or move the database aside and run: agentrouter init"
                    .into(),
            ),
        ),
    }
}

fn check_registry(home: &Path) -> Check {
    let reg = home.join("registry");
    let providers_path = reg.join("providers.yaml");
    let models_path = reg.join("models.yaml");
    let loaded = agentrouter_registry::load_providers(&providers_path).and_then(|providers| {
        let provider_count = providers.len();
        agentrouter_registry::load_models(&models_path, &providers)
            .map(|(models, _)| (provider_count, models.len()))
    });
    match loaded {
        Ok((provider_count, model_count)) => Check::new(
            "registry.load",
            OK,
            format!("{provider_count} provider(s), {model_count} model(s)"),
            None,
        ),
        Err(error) => Check::new(
            "registry.load",
            FAIL,
            format!(
                "registry is missing or invalid ({})",
                registry_error_kind(&error)
            ),
            Some("run: agentrouter init, or fix the YAML under ~/.agentrouter/registry".into()),
        ),
    }
}

fn registry_error_kind(error: &agentrouter_registry::RegistryError) -> &'static str {
    use agentrouter_registry::RegistryError;
    match error {
        RegistryError::NotFound(_) => "RegistryError",
        RegistryError::InvalidYaml(_, _) => "RegistryError",
        RegistryError::NotAMapping(_) => "RegistryError",
        RegistryError::InvalidProvider { .. } => "RegistryError",
        RegistryError::NoProviders(_) => "RegistryError",
        RegistryError::InvalidModel { .. } => "RegistryError",
        RegistryError::UnknownProvider { .. } => "RegistryError",
        RegistryError::NoModels(_) => "RegistryError",
        RegistryError::DuplicateModel { .. } => "RegistryError",
        RegistryError::OverridesNotAMapping(_) => "RegistryError",
        RegistryError::InvalidOverride { .. } => "RegistryError",
    }
}

fn check_catalogs(home: &Path) -> Check {
    let reg = home.join("registry");
    if !reg.is_dir() {
        return Check::new(
            "catalogs.generated",
            WARN,
            "no registry directory",
            Some("run: agentrouter init".into()),
        );
    }
    let paths = match std::fs::read_dir(&reg) {
        Ok(entries) => entries
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .filter(|path| {
                path.file_name()
                    .and_then(|name| name.to_str())
                    .is_some_and(|name| {
                        name.starts_with("models.") && name.ends_with(".generated.yaml")
                    })
            })
            .collect::<Vec<_>>(),
        Err(_) => {
            return Check::new(
                "catalogs.generated",
                FAIL,
                "registry directory cannot be read",
                Some("check registry directory permissions".into()),
            )
        }
    };
    if paths.is_empty() {
        return Check::new(
            "catalogs.generated",
            OK,
            "none refreshed; manual models.yaml is authoritative",
            None,
        );
    }
    match agentrouter_registry::catalog_ops::list_generated(&reg, Local::now().date_naive()) {
        Ok(statuses) if statuses.iter().any(|status| status.stale) => {
            let stale = statuses.iter().filter(|status| status.stale).count();
            Check::new(
                "catalogs.generated",
                WARN,
                format!("{stale} stale catalog(s)"),
                Some("run: agentrouter providers refresh <provider>".into()),
            )
        }
        Ok(statuses) => Check::new(
            "catalogs.generated",
            OK,
            format!("{} catalog(s), all fresh", statuses.len()),
            None,
        ),
        Err(_) => Check::new(
            "catalogs.generated",
            FAIL,
            "unreadable generated catalog(s)",
            Some("run: agentrouter providers doctor  (then providers rollback <provider>)".into()),
        ),
    }
}

fn check_hosts() -> Check {
    let mut ready = Vec::new();
    let mut remedies = Vec::new();
    for host in agentrouter_hosts::known_hosts() {
        let status = agentrouter_hosts::detect_host(host, None);
        if status.availability == agentrouter_hosts::AVAILABLE && host != "manual" {
            ready.push(host.to_owned());
        } else if let Some(remedy) = status.remedy {
            remedies.push(format!("{host}: {remedy}"));
        }
    }
    ready.sort();
    if !ready.is_empty() {
        return Check::new(
            "hosts.ready",
            OK,
            format!("ready: {}", ready.join(", ")),
            None,
        );
    }
    Check::new(
        "hosts.ready",
        WARN,
        "no execution host is ready; only manual execution is available",
        remedies
            .first()
            .cloned()
            .or_else(|| Some("run: agentrouter hosts doctor".into())),
    )
}

fn check_api_key() -> Check {
    match std::env::var("AGENTROUTER_API_KEY") {
        Err(_) => Check::new(
            "server.auth",
            WARN,
            "AGENTROUTER_API_KEY is unset; the local API is open",
            Some("set AGENTROUTER_API_KEY to require an X-API-Key header".into()),
        ),
        Ok(value) if value.trim().is_empty() => Check::new(
            "server.auth",
            FAIL,
            "AGENTROUTER_API_KEY is set but blank",
            Some("unset it, or set it to a real value — a blank key rejects every request".into()),
        ),
        Ok(_) => Check::new("server.auth", OK, "AGENTROUTER_API_KEY is set", None),
    }
}

fn check_observability() -> Check {
    let logging = truthy(std::env::var("AGENTROUTER_LOG").ok());
    let detail = format!(
        "structured logging {}, OTel off",
        if logging { "on" } else { "off" }
    );
    Check::new(
        "observability.logging",
        OK,
        detail,
        (!logging).then(|| "set AGENTROUTER_LOG=1 to emit structured route records".into()),
    )
}

fn check_plugins() -> Check {
    Check::new(
        "plugins.state",
        WARN,
        "Rust plugin health checks are not ported",
        Some("use the Python agentrouter plugin doctor for plugin diagnostics".into()),
    )
}

fn check_server_extra() -> Check {
    Check::new(
        "server.extra",
        WARN,
        "the REST API is not part of the Rust CLI yet",
        Some("use the Python agentrouter server entrypoint".into()),
    )
}

fn check_usage(host: &str) -> Check {
    let env_name = match host {
        "anthropic-api" => "ANTHROPIC_API_KEY",
        "openai-api" => "OPENAI_API_KEY",
        "gemini-api" => "GOOGLE_API_KEY",
        "openrouter" => "OPENROUTER_API_KEY",
        _ => {
            return Check::new(
                &format!("usage.{host}"),
                OK,
                "not authenticated; usage not checked",
                None,
            )
        }
    };
    let authenticated = std::env::var(env_name).is_ok_and(|value| !value.trim().is_empty());
    if authenticated {
        Check::new(
            &format!("usage.{host}"),
            OK,
            "unsupported: no live usage adapter is registered",
            None,
        )
    } else {
        Check::new(
            &format!("usage.{host}"),
            OK,
            "not authenticated; usage not checked",
            None,
        )
    }
}

pub fn run_all(home: &Path) -> Vec<Check> {
    let harness = crate::harness::detect_harness();
    vec![
        safe("app.version", || {
            Check::new(
                "app.version",
                OK,
                format!("agentrouter-rust-cli {}", env!("CARGO_PKG_VERSION")),
                None,
            )
        }),
        safe("runtime.rust", || {
            Check::new(
                "runtime.rust",
                OK,
                format!(
                    "Rust {} on {}",
                    env!("CARGO_PKG_VERSION"),
                    std::env::consts::OS
                ),
                None,
            )
        }),
        safe("data.home", || check_home(home)),
        safe("data.database", || check_database(home)),
        safe("registry.load", || check_registry(home)),
        safe("catalogs.generated", || check_catalogs(home)),
        safe("hosts.ready", check_hosts),
        safe("environment.harness", || {
            Check::new(
                "environment.harness",
                OK,
                format!("{} ({})", harness.name, harness.evidence),
                None,
            )
        }),
        safe("plugins.state", check_plugins),
        safe("server.extra", check_server_extra),
        safe("server.auth", check_api_key),
        safe("contract.version", || {
            Check::new("contract.version", OK, "HTTP contract v1", None)
        }),
        safe("observability.logging", check_observability),
    ]
}

pub fn run_usage_checks() -> Vec<Check> {
    agentrouter_hosts::api_hosts()
        .into_iter()
        .map(|host| safe(&format!("usage.{host}"), || check_usage(host)))
        .collect()
}

pub fn worst(checks: &[Check]) -> &'static str {
    if checks.iter().any(|check| check.status == FAIL) {
        FAIL
    } else if checks.iter().any(|check| check.status == WARN) {
        WARN
    } else {
        OK
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn worst_is_failure_then_warning_then_ok() {
        assert_eq!(worst(&[]), OK);
        assert_eq!(worst(&[Check::new("x", WARN, "warning", None)]), WARN);
        assert_eq!(
            worst(&[
                Check::new("x", WARN, "warning", None),
                Check::new("y", FAIL, "failure", Some("fix".into()))
            ]),
            FAIL
        );
    }

    #[test]
    fn missing_database_is_actionable_warning() {
        let path = std::env::temp_dir().join(format!(
            "agentrouter-doctor-missing-db-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&path).unwrap();
        let check = check_database(&path);
        std::fs::remove_dir_all(path).unwrap();
        assert_eq!(check.status, WARN);
        assert!(check.remedy.is_some());
    }
}
