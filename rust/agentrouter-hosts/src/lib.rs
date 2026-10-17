//! Rust port of `agentrouter/hosts.py` — execution-host discovery and
//! two-stage host resolution. Read-only, offline-safe, never reads or
//! prints a credential value. Field-for-field with the Python module; see
//! its module docstring for the availability/state vocabulary this mirrors.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use agentrouter_registry::{ExecutionTarget, ModelEntry};
use serde::Serialize;

pub const AVAILABLE: &str = "available";
pub const UNAVAILABLE: &str = "unavailable";
pub const UNKNOWN: &str = "unknown";

pub const MISSING: &str = "missing";
pub const INSTALLED: &str = "installed";
pub const CONFIGURED: &str = "configured";
pub const AUTHENTICATED: &str = "authenticated";
pub const AUTHORIZED: &str = "authorized";
pub const DEGRADED: &str = "degraded";
pub const STATE_UNKNOWN: &str = UNKNOWN;

fn is_available_state(s: &str) -> bool {
    matches!(s, INSTALLED | CONFIGURED | AUTHENTICATED | AUTHORIZED)
}
fn is_unavailable_state(s: &str) -> bool {
    matches!(s, MISSING | DEGRADED)
}

struct CliHost {
    command: &'static str,
    config_dir: &'static str,
    credential_files: &'static [&'static str],
    env_fallback: &'static [&'static str],
}

fn cli_hosts() -> &'static HashMap<&'static str, CliHost> {
    use std::sync::OnceLock;
    static CELL: OnceLock<HashMap<&'static str, CliHost>> = OnceLock::new();
    CELL.get_or_init(|| {
        HashMap::from([
            (
                "claude-code",
                CliHost {
                    command: "claude",
                    config_dir: ".claude",
                    credential_files: &[".credentials.json"],
                    env_fallback: &["ANTHROPIC_API_KEY"],
                },
            ),
            (
                "codex-cli",
                CliHost {
                    command: "codex",
                    config_dir: ".codex",
                    credential_files: &["auth.json"],
                    env_fallback: &["OPENAI_API_KEY"],
                },
            ),
        ])
    })
}

fn api_hosts_map() -> &'static HashMap<&'static str, &'static str> {
    use std::sync::OnceLock;
    static CELL: OnceLock<HashMap<&'static str, &'static str>> = OnceLock::new();
    CELL.get_or_init(|| {
        HashMap::from([
            ("anthropic-api", "ANTHROPIC_API_KEY"),
            ("openai-api", "OPENAI_API_KEY"),
            ("gemini-api", "GOOGLE_API_KEY"),
            ("openrouter", "OPENROUTER_API_KEY"),
        ])
    })
}

fn install_hint(host: &str) -> String {
    match host {
        "claude-code" => "install Claude Code, then run: claude login".to_string(),
        "codex-cli" => "install the Codex CLI, then authenticate it".to_string(),
        _ => "install it and make sure it is on PATH".to_string(),
    }
}

fn auth_hint(host: &str, shown: &str) -> String {
    match host {
        "claude-code" => "run: claude login".to_string(),
        "codex-cli" => "authenticate the Codex CLI".to_string(),
        _ => format!("authenticate '{shown}'"),
    }
}

fn availability_for(state: &str) -> &'static str {
    if is_available_state(state) {
        AVAILABLE
    } else if is_unavailable_state(state) {
        UNAVAILABLE
    } else {
        UNKNOWN
    }
}

/// Indirection so tests can point this at a tempdir instead of the real
/// home, mirroring Python's `_home_dir()` seam. Checks `AGENTROUTER_HOME`
/// first (test/CI override only), then falls back to the real platform
/// home dir.
fn home_dir() -> PathBuf {
    if let Ok(over) = std::env::var("AGENTROUTER_HOME") {
        return PathBuf::from(over);
    }
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn safe_exists(path: &Path) -> bool {
    path.try_exists().unwrap_or(false)
}

fn safe_is_dir(path: &Path) -> bool {
    path.metadata().map(|m| m.is_dir()).unwrap_or(false)
}

/// Strip control/escape characters from text echoed to a terminal, same
/// defense as Python's `_sanitize`.
fn sanitize(value: &str) -> String {
    value
        .chars()
        .filter(|c| !c.is_control())
        .take(120)
        .collect()
}

fn env_is_set(name: &str) -> bool {
    std::env::var(name)
        .map(|v| !v.trim().is_empty())
        .unwrap_or(false)
}

fn env_is_blank(name: &str) -> bool {
    match std::env::var(name) {
        Ok(v) => v.trim().is_empty(),
        Err(_) => false,
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct HostStatus {
    pub host: String,
    pub availability: String,
    pub reason: String,
    pub state: String,
    pub remedy: Option<String>,
}

fn status(host: &str, state: &str, reason: String, remedy: Option<String>) -> HostStatus {
    HostStatus {
        host: host.to_string(),
        availability: availability_for(state).to_string(),
        reason,
        state: state.to_string(),
        remedy,
    }
}

/// Cheapest-fix-first ordering for diagnostics. Not a security boundary.
pub fn fix_cost(s: &HostStatus) -> u8 {
    if s.state == DEGRADED {
        return 0;
    }
    if s.state == MISSING {
        return if api_hosts_map().contains_key(s.host.as_str()) {
            1
        } else {
            2
        };
    }
    3
}

fn detect_cli_host(host: &str, meta: Option<&CliHost>, cmd: &str) -> HostStatus {
    let shown = sanitize(cmd);
    if which::which(cmd).is_err() {
        let hint = install_hint(host);
        return status(
            host,
            MISSING,
            format!("'{shown}' not found on PATH"),
            Some(hint),
        );
    }
    let Some(meta) = meta else {
        return status(host, INSTALLED, format!("'{shown}' found on PATH"), None);
    };

    let home = home_dir();
    for cred in meta.credential_files {
        if safe_exists(&home.join(meta.config_dir).join(cred)) {
            return status(
                host,
                AUTHENTICATED,
                format!(
                    "'{shown}' on PATH; credentials found in ~/{}",
                    meta.config_dir
                ),
                None,
            );
        }
    }
    for env in meta.env_fallback {
        if env_is_set(env) {
            return status(
                host,
                AUTHENTICATED,
                format!("'{shown}' on PATH; {env} is set"),
                None,
            );
        }
    }
    if safe_is_dir(&home.join(meta.config_dir)) {
        return status(
            host,
            CONFIGURED,
            format!(
                "'{shown}' on PATH; ~/{} exists but no credentials found",
                meta.config_dir
            ),
            Some(auth_hint(host, &shown)),
        );
    }
    for env in meta.env_fallback {
        if env_is_blank(env) {
            return status(
                host,
                DEGRADED,
                format!("'{shown}' on PATH but {env} is set to an empty value"),
                Some(format!("unset {env}, or set it to a real key")),
            );
        }
    }
    status(
        host,
        INSTALLED,
        format!("'{shown}' found on PATH; not configured yet"),
        Some(auth_hint(host, &shown)),
    )
}

fn detect_api_host(host: &str, env: &str) -> HostStatus {
    if env_is_blank(env) {
        return status(
            host,
            DEGRADED,
            format!("{env} is set but empty"),
            Some(format!(
                "set {env} to a real key, or unset it to use another host"
            )),
        );
    }
    if env_is_set(env) {
        return status(host, AUTHENTICATED, format!("{env} is set"), None);
    }
    status(
        host,
        MISSING,
        format!("{env} is not set"),
        Some(format!("export {env}=<your key>")),
    )
}

/// Read-only readiness check for one host. Never runs the tool or reads secrets.
pub fn detect_host(host: &str, required_command: Option<&str>) -> HostStatus {
    if host == "manual" {
        return status(
            host,
            CONFIGURED,
            "manual execution is always available".to_string(),
            None,
        );
    }
    let meta = cli_hosts().get(host);
    let cmd = required_command.or(meta.map(|m| m.command));
    let is_api = api_hosts_map().contains_key(host);
    if meta.is_some() || (required_command.is_some() && !is_api) {
        return match cmd {
            None => status(
                host,
                STATE_UNKNOWN,
                "no command declared; cannot verify".to_string(),
                None,
            ),
            Some(cmd) => detect_cli_host(host, meta, cmd),
        };
    }
    if let Some(env) = api_hosts_map().get(host) {
        return detect_api_host(host, env);
    }
    status(
        host,
        STATE_UNKNOWN,
        "unrecognized host; cannot verify availability".to_string(),
        Some("check the host id in your registry, or run: agentrouter hosts list".to_string()),
    )
}

pub fn target_status(t: &ExecutionTarget) -> HostStatus {
    detect_host(&t.host, t.required_command.as_deref())
}

#[derive(Debug, Clone)]
pub struct ResolvedRoute<'a> {
    pub target: Option<&'a ExecutionTarget>,
    pub status: Option<HostStatus>,
    pub all_statuses: Vec<HostStatus>,
}

impl ResolvedRoute<'_> {
    pub fn is_available(&self) -> bool {
        self.status
            .as_ref()
            .map(|s| s.availability == AVAILABLE)
            .unwrap_or(false)
    }
}

/// Picks the best execution target for a model. Prefers the first target
/// whose host is available; if none is, returns the first target marked
/// unavailable (when `include_unavailable`) so the caller can show it as
/// "global best, not runnable here".
pub fn resolve_execution_route(model: &ModelEntry, include_unavailable: bool) -> ResolvedRoute<'_> {
    let statuses: Vec<HostStatus> = model.execution_targets.iter().map(target_status).collect();
    for (t, s) in model.execution_targets.iter().zip(statuses.iter()) {
        if s.availability == AVAILABLE {
            return ResolvedRoute {
                target: Some(t),
                status: Some(s.clone()),
                all_statuses: statuses,
            };
        }
    }
    if let Some(first) = model.execution_targets.first() {
        return ResolvedRoute {
            target: if include_unavailable {
                Some(first)
            } else {
                None
            },
            status: statuses.first().cloned(),
            all_statuses: statuses,
        };
    }
    ResolvedRoute {
        target: None,
        status: None,
        all_statuses: statuses,
    }
}

/// Human-readable command preview; the prompt is redacted by default.
pub fn command_preview(target: &ExecutionTarget, redact: bool) -> String {
    match &target.command_template {
        None => format!(
            "(no command - {} host '{}')",
            format!("{:?}", target.execution_mode).to_lowercase(),
            target.host
        ),
        Some(template) => template
            .iter()
            .map(|a| {
                if redact && a == "{prompt}" {
                    "<prompt redacted>".to_string()
                } else {
                    a.clone()
                }
            })
            .collect::<Vec<_>>()
            .join(" "),
    }
}

pub fn known_hosts() -> Vec<&'static str> {
    let mut v: Vec<&'static str> = cli_hosts().keys().copied().collect();
    v.extend(api_hosts_map().keys().copied());
    v.push("manual");
    v
}

pub fn api_hosts() -> Vec<&'static str> {
    api_hosts_map().keys().copied().collect()
}

pub fn provider_for_api_host(host: &str) -> Option<&'static str> {
    match host {
        "anthropic-api" => Some("anthropic"),
        "openai-api" => Some("openai"),
        "gemini-api" => Some("google"),
        "openrouter" => Some("openrouter"),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    // These tests mutate process-global env vars, so they must not run
    // concurrently with each other (cargo test runs them on threads by
    // default) — a single mutex serializes the whole module's tests.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn manual_host_is_always_configured() {
        let _g = ENV_LOCK.lock().unwrap();
        let s = detect_host("manual", None);
        assert_eq!(s.state, CONFIGURED);
        assert_eq!(s.availability, AVAILABLE);
    }

    #[test]
    fn unknown_host_is_state_unknown() {
        let _g = ENV_LOCK.lock().unwrap();
        let s = detect_host("made-up-host", None);
        assert_eq!(s.state, STATE_UNKNOWN);
        assert_eq!(s.availability, UNKNOWN);
    }

    #[test]
    fn api_host_missing_without_env_var() {
        let _g = ENV_LOCK.lock().unwrap();
        std::env::remove_var("OPENROUTER_API_KEY");
        let s = detect_host("openrouter", None);
        assert_eq!(s.state, MISSING);
    }

    #[test]
    fn api_host_authenticated_with_env_var() {
        let _g = ENV_LOCK.lock().unwrap();
        std::env::set_var("OPENROUTER_API_KEY", "sk-test");
        let s = detect_host("openrouter", None);
        std::env::remove_var("OPENROUTER_API_KEY");
        assert_eq!(s.state, AUTHENTICATED);
    }

    #[test]
    fn api_host_degraded_when_blank() {
        let _g = ENV_LOCK.lock().unwrap();
        std::env::set_var("OPENROUTER_API_KEY", "   ");
        let s = detect_host("openrouter", None);
        std::env::remove_var("OPENROUTER_API_KEY");
        assert_eq!(s.state, DEGRADED);
    }

    #[test]
    fn cli_host_missing_binary() {
        let _g = ENV_LOCK.lock().unwrap();
        let s = detect_host("claude-code", Some("definitely-not-a-real-binary-xyz"));
        assert_eq!(s.state, MISSING);
    }
}
