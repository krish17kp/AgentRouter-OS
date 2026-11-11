//! Rust port of the `agentrouter route --json` pipeline: the parts of
//! `agentrouter/cli.py`'s `route()` command not already covered by another
//! crate, namely `safety.gates_for`, `prompts.generate_prompt`,
//! `learning.learned_weights`, `cli._apply_policy`/`_reason_for`, plus the
//! orchestration that assembles the final JSON payload. Registries,
//! classification, routing, controls, and host resolution are all delegated
//! to their own already-ported crates. See `tests/test_cli_route_rust_compat.py`.
//!
//! Scope note: this covers `route --json` with config.yaml routing overrides
//! and hard controls, but no `--verify-live` (a documented no-op today since
//! no live usage adapter is registered — see `agentrouter-usage`). `init`,
//! `explain`, `feedback`, `registry list`, `prompt generate`, `plugin`, and
//! `providers *` are not ported in this slice.

use std::collections::HashMap;
use std::io::{Read, Write};
use std::path::{Component, Path, PathBuf};

use agentrouter_core::{ApprovalLevel, Classification, Level};
use agentrouter_registry::ModelEntry;
use agentrouter_routing::RouteResult;
use serde_json::{json, Value};

pub mod dashboard;
pub mod harness;
pub mod observability;
pub mod openai;

/// Mirrors `safety._CHECKLISTS` + `safety.gates_for`.
pub fn gates_for(cls: &Classification) -> Value {
    let checklist: Vec<&'static str> = match cls.risk {
        Level::Low => vec!["Sanity-check the output before using it"],
        Level::Medium => vec![
            "Review the output before acting on it",
            "Run relevant tests / verify behavior",
            "Confirm the change stays within intended scope",
        ],
        Level::High => vec![
            "Review full diff before applying",
            "Run the test suite",
            "Secret scan changed files",
            "Confirm rollback path",
            "Human sign-off (no auto-execute)",
        ],
    };
    let auto_execute_allowed = cls.risk != Level::High && cls.approval_level == ApprovalLevel::Auto;
    json!({
        "checklist": checklist,
        "auto_execute_allowed": auto_execute_allowed,
        "approval_level": serde_json::to_value(cls.approval_level).unwrap(),
    })
}

/// Mirrors `prompts.generate_prompt`.
pub fn generate_prompt(
    task: &str,
    tool_key: &str,
    cls: &Classification,
    checklist: &[Value],
) -> String {
    let approval: String = serde_json::to_value(cls.approval_level)
        .unwrap()
        .as_str()
        .unwrap()
        .to_string();
    let risk_line = if approval == "human-approval-required" {
        "4. STOP before any irreversible action - this task requires human approval."
    } else {
        "4. Flag anything unexpected instead of guessing."
    };
    let tools = if cls.tool_needs.is_empty() {
        "none".to_string()
    } else {
        cls.tool_needs.join(", ")
    };
    let checklist_lines = checklist
        .iter()
        .map(|c| format!("- [ ] {}", c.as_str().unwrap_or_default()))
        .collect::<Vec<_>>()
        .join("\n");

    format!(
        "# Execution Prompt\n\n\
Target tool: {tool_key}\n\n\
## Task\n{task}\n\n\
## Context for the executing tool\n\
- Task type: {task_type} | Complexity: {complexity} | Risk: {risk}\n\
- Expected output: {output_type}\n\
- Estimated context: ~{context_tokens} tokens ({context_band})\n\
- Tools you may need: {tools}\n\n\
## Instructions\n\
1. Restate the task in your own words before starting.\n\
2. Produce the expected output type ({output_type}).\n\
3. Keep changes minimal and within the stated scope.\n\
{risk_line}\n\n\
## Safety checklist (complete before applying results)\n\
{checklist_lines}\n",
        task_type = serde_json::to_value(cls.task_type)
            .unwrap()
            .as_str()
            .unwrap(),
        complexity = serde_json::to_value(cls.complexity)
            .unwrap()
            .as_str()
            .unwrap(),
        risk = serde_json::to_value(cls.risk).unwrap().as_str().unwrap(),
        output_type = serde_json::to_value(cls.output_type)
            .unwrap()
            .as_str()
            .unwrap(),
        context_tokens = cls.context_tokens,
        context_band = serde_json::to_value(cls.context_band)
            .unwrap()
            .as_str()
            .unwrap(),
    )
}

/// Reuse the recorded prompt unless the caller explicitly chooses another
/// tool. An override regenerates from the stored task, classification, and
/// checklist, matching `prompt generate --from` without re-routing.
pub fn prompt_from_decision(payload: &Value, tool: Option<&str>) -> Result<String, String> {
    if let Some(tool) = tool {
        if tool.is_empty() {
            return Err("target tool must not be empty".to_string());
        }
        let task = payload["task"]
            .as_str()
            .ok_or_else(|| "stored decision has no task".to_string())?;
        let cls: Classification = serde_json::from_value(payload["classification"].clone())
            .map_err(|_| "stored decision has invalid classification".to_string())?;
        let checklist = payload["gates"]["checklist"]
            .as_array()
            .ok_or_else(|| "stored decision has no safety checklist".to_string())?;
        if !checklist.iter().all(Value::is_string) {
            return Err("stored decision has invalid safety checklist".to_string());
        }
        return Ok(generate_prompt(task, tool, &cls, checklist));
    }
    payload["prompt"]
        .as_str()
        .map(str::to_string)
        .ok_or_else(|| "stored decision has no prompt".to_string())
}

const MIN_FEEDBACK: i64 = 3;
const STEP: f64 = 0.01;
const MAX_SHIFT: f64 = 0.10;
const MIN_W_COST: f64 = 0.05;
const NEGATIVE_AT_OR_BELOW: i64 = 2;

/// Mirrors `learning.learned_weights`.
pub fn learned_weights(
    conn: &rusqlite::Connection,
    base: &agentrouter_routing::Weights,
) -> rusqlite::Result<(agentrouter_routing::Weights, Option<String>)> {
    let (total, negative): (i64, i64) = conn.query_row(
        "SELECT COUNT(*), COALESCE(SUM(rating <= ?1), 0) FROM feedback WHERE rating IS NOT NULL",
        rusqlite::params![NEGATIVE_AT_OR_BELOW],
        |r| Ok((r.get(0)?, r.get(1)?)),
    )?;
    if total < MIN_FEEDBACK || negative == 0 {
        return Ok((*base, None));
    }
    let shift = (STEP * negative as f64)
        .min(MAX_SHIFT)
        .min(base.w_cost - MIN_W_COST);
    if shift <= 0.0 {
        return Ok((*base, None));
    }
    let w = agentrouter_routing::Weights {
        w_cap: (base.w_cap + shift * 10000.0).round() / 10000.0,
        w_cost: (base.w_cost - shift * 10000.0).round() / 10000.0,
        ..*base
    };
    let note = format!(
        "learned from {total} rating(s), {negative} negative -> w_cap +{shift:.2}, w_cost -{shift:.2} (delete feedback or set learning: false to revert)"
    );
    Ok((w, Some(note)))
}

/// Mirrors `cli._apply_policy`'s pricing-tier cap. Returns `Err` with the
/// same message Python would print on an invalid `policy.max_pricing_tier`.
pub fn apply_policy(
    models: Vec<ModelEntry>,
    max_tier: Option<&str>,
) -> Result<Vec<ModelEntry>, String> {
    let Some(max_tier) = max_tier else {
        return Ok(models);
    };
    let tiers = ["free", "low", "medium", "high", "frontier"];
    let Some(cap) = tiers.iter().position(|t| *t == max_tier) else {
        return Err(format!(
            "Config error: policy.max_pricing_tier '{max_tier}' is not one of {tiers:?}."
        ));
    };
    Ok(models
        .into_iter()
        .filter(|m| {
            let tier_str = serde_json::to_value(m.pricing_tier).unwrap();
            let idx = tiers
                .iter()
                .position(|t| *t == tier_str.as_str().unwrap())
                .unwrap();
            idx <= cap
        })
        .collect())
}

/// Load the routing-relevant subset of `config.yaml`. Python accepts unknown
/// top-level keys and ignores nonnumeric individual weight overrides; the
/// Rust probe follows those rules while rejecting a malformed YAML document
/// or non-mapping policy before a route is produced.
pub fn load_route_config(
    home: &Path,
) -> Result<(agentrouter_routing::Weights, bool, Option<String>), String> {
    let path = home.join("config.yaml");
    let contents = match std::fs::read_to_string(&path) {
        Ok(contents) => contents,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(error) => return Err(error.to_string()),
    };
    let config: Value = if contents.trim().is_empty() {
        json!({})
    } else {
        serde_yaml::from_str(&contents).map_err(|error| format!("invalid config YAML: {error}"))?
    };
    let config = if config.is_null() { json!({}) } else { config };
    let map = config
        .as_object()
        .ok_or_else(|| "config.yaml must be a YAML mapping".to_string())?;
    let mut weights = agentrouter_routing::Weights::default();
    let overrides = match map.get("weights") {
        None | Some(Value::Null) => None,
        Some(Value::Object(overrides)) => Some(overrides),
        Some(_) => return Err("Config error: 'weights' must be a mapping.".to_string()),
    };
    if let Some(overrides) = overrides {
        for name in ["w_cap", "w_cost", "w_lat", "w_ctx"] {
            if overrides.get(name).is_some_and(Value::is_boolean) {
                return Err(format!("Config error: weight '{name}' must be numeric."));
            }
            if let Some(value) = overrides.get(name).and_then(Value::as_f64) {
                match name {
                    "w_cap" => weights.w_cap = value,
                    "w_cost" => weights.w_cost = value,
                    "w_lat" => weights.w_lat = value,
                    "w_ctx" => weights.w_ctx = value,
                    _ => unreachable!(),
                }
            }
        }
    }
    let policy = match map.get("policy") {
        None | Some(Value::Null) => None,
        Some(Value::Object(policy)) => match policy.get("max_pricing_tier") {
            None | Some(Value::Null) => None,
            Some(Value::String(tier)) => Some(tier.clone()),
            Some(_) => return Err("Config error: invalid policy.max_pricing_tier".to_string()),
        },
        Some(_) => return Err("Config error: 'policy' must be a mapping.".to_string()),
    };
    let learning = map.get("learning") != Some(&Value::Bool(false));
    Ok((weights, learning, policy))
}

/// Mirrors `cli._reason_for`.
pub fn reason_for(rec: &Value, cls: &Classification, shifts: &[String]) -> String {
    let t = &rec["terms"];
    let task_type = serde_json::to_value(cls.task_type)
        .unwrap()
        .as_str()
        .unwrap()
        .to_string();
    let mut parts = vec![format!(
        "strongest weighted fit for {task_type} (capability {}, cost-fit {}, context-fit {})",
        t["cap"], t["cost"], t["ctx"]
    )];
    if t["adj"].as_f64().unwrap_or(0.0) > 0.0 {
        parts.push("ideal-use-case match".to_string());
    }
    if !cls.tool_needs.is_empty() {
        parts.push(format!(
            "supports required tools: {}",
            cls.tool_needs.join(", ")
        ));
    }
    for s in shifts {
        if s.contains("quota exhausted") {
            parts.push("previous top pick skipped: quota exhausted (live-verified)".to_string());
        } else if s.contains("high") {
            parts.push("capability weighted up (high complexity/risk)".to_string());
        } else if s.contains("low") {
            parts.push("cost weighted up (simple task)".to_string());
        } else if s.contains("large") {
            parts.push("context fit weighted up (large input)".to_string());
        }
    }
    parts.join("; ")
}

/// Mirrors `hosts.execution_route_block`.
pub fn execution_route_block(
    row: Option<&Value>,
    models_by_key: &HashMap<String, &ModelEntry>,
) -> Value {
    let Some(row) = row else {
        return Value::Null;
    };
    let Some(model_key) = row["model"].as_str() else {
        return Value::Null;
    };
    let Some(model) = models_by_key.get(model_key) else {
        return Value::Null;
    };
    if model.execution_targets.is_empty() {
        return Value::Null;
    }
    let resolved = agentrouter_hosts::resolve_execution_route(model, true);
    let tgt = resolved.target;
    let status = resolved.status.as_ref();
    json!({
        "vendor": model.vendor(),
        "model_id": model.model_id,
        "display_name": model.name(),
        "release_channel": serde_json::to_value(model.release_channel).unwrap(),
        "host": tgt.map(|t| t.host.clone()),
        "host_model_id": tgt.map(|t| t.host_model_id.clone()),
        "execution_mode": tgt.map(|t| serde_json::to_value(t.execution_mode).unwrap()),
        "availability": status.map(|s| s.availability.clone()).unwrap_or_else(|| "unknown".to_string()),
        "availability_reason": status.map(|s| s.reason.clone()).unwrap_or_else(|| "no execution target".to_string()),
        "host_state": status.map(|s| s.state.clone()).unwrap_or_else(|| agentrouter_hosts::STATE_UNKNOWN.to_string()),
        "host_remedy": status.and_then(|s| s.remedy.clone()),
        "command_preview": tgt.map(|t| agentrouter_hosts::command_preview(t, true)),
        "required_env": tgt.map(|t| t.required_env.clone()).unwrap_or_default(),
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "all_hosts": resolved.all_statuses.iter().map(|s| json!({
            "host": s.host,
            "availability": s.availability,
            "state": s.state,
        })).collect::<Vec<_>>(),
    })
}

/// Full `route --json` orchestration: classify, filter/score, assemble the
/// same payload shape `cli.route()` builds (minus `decision_id`, added by
/// the caller after optionally persisting it).
pub fn route_payload(
    task: &str,
    models: &[ModelEntry],
    cls: &Classification,
    base_weights: agentrouter_routing::Weights,
    prefer: Option<&str>,
    weight_shift_note: Option<String>,
) -> Value {
    let result: RouteResult = agentrouter_routing::route(models, cls, base_weights, prefer);
    let mut result_json = serde_json::to_value(&result).unwrap();
    if let Some(note) = weight_shift_note {
        result_json["weight_shifts"]
            .as_array_mut()
            .unwrap()
            .push(Value::String(note));
    }

    let models_by_key: HashMap<String, &ModelEntry> = models.iter().map(|m| (m.key(), m)).collect();
    let rec = &result_json["recommendation"];
    let target = if !rec.is_null() {
        rec["model"].as_str().unwrap().to_string()
    } else {
        result_json["manual_suggestion"]
            .as_str()
            .map(str::to_string)
            .unwrap_or_else(|| "manual/human-operator".to_string())
    };
    let gates = gates_for(cls);
    let checklist = gates["checklist"].as_array().unwrap();
    let prompt = generate_prompt(task, &target, cls, checklist);
    let reason = if !rec.is_null() {
        let shifts: Vec<String> = result_json["weight_shifts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().to_string())
            .collect();
        Value::String(reason_for(rec, cls, &shifts))
    } else {
        Value::Null
    };
    let exec_route = if !rec.is_null() {
        execution_route_block(Some(rec), &models_by_key)
    } else {
        Value::Null
    };
    let fb_route = if !result_json["fallback"].is_null() {
        execution_route_block(Some(&result_json["fallback"]), &models_by_key)
    } else {
        Value::Null
    };

    let mut payload = json!({
        "classification": serde_json::to_value(cls).unwrap(),
    });
    for (k, v) in result_json.as_object().unwrap() {
        payload[k] = v.clone();
    }
    payload["reason"] = reason;
    payload["gates"] = gates;
    payload["prompt"] = Value::String(prompt);
    payload["execution_route"] = exec_route;
    payload["fallback_execution_route"] = fb_route;
    payload
}

/// Apply user hard controls before scoring and retain every control exclusion
/// ahead of engine exclusions, matching Python's `route` command trail.
pub fn route_payload_with_controls(
    task: &str,
    models: &[ModelEntry],
    cls: &Classification,
    base_weights: agentrouter_routing::Weights,
    prefer: Option<&str>,
    weight_shift_note: Option<String>,
    controls: &agentrouter_policy::controls::RouteControls,
) -> Value {
    let (kept, dropped) = agentrouter_policy::controls::apply_controls(models, controls);
    let mut payload = route_payload(task, &kept, cls, base_weights, prefer, weight_shift_note);
    if !dropped.is_empty() {
        let mut excluded: Vec<Value> = dropped
            .into_iter()
            .map(|item| json!({"model": item.model, "reason": item.reason}))
            .collect();
        excluded.extend(payload["excluded"].as_array().cloned().unwrap_or_default());
        payload["excluded"] = json!(excluded);
    }
    payload
}

/// `_home()`: `AGENTROUTER_HOME` env var, else `~/.agentrouter`.
pub fn home_dir() -> std::path::PathBuf {
    std::env::var("AGENTROUTER_HOME")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| dirs_home().join(".agentrouter"))
}

/// Seed a new local home without replacing existing files. `create_new`
/// avoids following a symlink or clobbering a file created between the
/// existence check and the write. The seed bytes are embedded so the Rust
/// binary does not require the Python package at runtime.
pub fn init_home(home: &Path) -> Result<Vec<String>, String> {
    init_home_with_force(home, false)
}

fn is_link_or_reparse(metadata: &std::fs::Metadata) -> bool {
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        // FILE_ATTRIBUTE_REPARSE_POINT includes junctions, not only symlinks.
        metadata.file_attributes() & 0x400 != 0
    }
    #[cfg(not(windows))]
    {
        false
    }
}

fn open_directory_child(parent: &std::fs::File, name: &Path) -> Result<std::fs::File, String> {
    let mut options = fs_at::OpenOptions::default();
    options.read(true).follow(false);
    let opened = match options.open_dir_at(parent, name) {
        Ok(opened) => opened,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            match options.mkdir_at(parent, name) {
                Ok(_) => {}
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {}
                Err(error) => return Err(error.to_string()),
            }
            options
                .open_dir_at(parent, name)
                .map_err(|e| format!("open directory {}: {e}", name.display()))?
        }
        Err(error) => return Err(format!("open directory {}: {error}", name.display())),
    };
    if is_link_or_reparse(&opened.metadata().map_err(|e| e.to_string())?) {
        return Err(format!("unsafe linked path: {}", name.display()));
    }
    Ok(opened)
}

fn open_safe_home(home: &Path) -> Result<std::fs::File, String> {
    let absolute = if home.is_absolute() {
        home.to_path_buf()
    } else {
        std::env::current_dir()
            .map_err(|e| e.to_string())?
            .join(home)
    };
    let mut root = PathBuf::new();
    let mut names = Vec::new();
    for component in absolute.components() {
        match component {
            Component::Prefix(prefix) => root.push(prefix.as_os_str()),
            Component::RootDir => root.push(component.as_os_str()),
            Component::Normal(name) => names.push(name.to_os_string()),
            Component::CurDir => {}
            Component::ParentDir => return Err("home path cannot contain '..'".to_string()),
        }
    }
    let mut current = cap_std::fs::Dir::open_ambient_dir(&root, cap_std::ambient_authority())
        .map_err(|e| format!("open root {}: {e}", root.display()))?
        .into_std_file();
    for name in names {
        current = open_directory_child(&current, Path::new(&name))?;
    }
    Ok(current)
}

fn atomic_replace<R: Read>(
    parent: &cap_std::fs::Dir,
    name: &Path,
    contents: &mut R,
    permissions: Option<&cap_std::fs::Permissions>,
) -> Result<(), String> {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let mut temporary_name = None;
    let mut temporary = None;
    for _ in 0..16 {
        let candidate = format!(
            ".agentrouter-init-{}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_err(|e| e.to_string())?
                .as_nanos(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        );
        let mut options = cap_std::fs::OpenOptions::new();
        options.write(true).create_new(true);
        match parent.open_with(&candidate, &options) {
            Ok(file) => {
                temporary_name = Some(candidate);
                temporary = Some(file);
                break;
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(error.to_string()),
        }
    }
    let temporary_name = temporary_name.ok_or("could not create a unique seed file")?;
    let mut temporary = temporary.ok_or("could not create a unique seed file")?;
    let result = (|| {
        std::io::copy(contents, &mut temporary).map_err(|e| e.to_string())?;
        if let Some(permissions) = permissions {
            temporary
                .set_permissions(permissions.clone())
                .map_err(|e| e.to_string())?;
        }
        drop(temporary);
        parent
            .rename(&temporary_name, parent, name)
            .map_err(|e| e.to_string())
    })();
    if result.is_err() {
        let _ = parent.remove_file(&temporary_name);
    }
    result
}

fn has_multiple_links(
    home_dir: &cap_std::fs::Dir,
    name: &str,
    metadata: &cap_std::fs::Metadata,
) -> Result<bool, String> {
    #[cfg(unix)]
    {
        use cap_std::fs::MetadataExt;
        let _ = (home_dir, name);
        Ok(metadata.nlink() > 1)
    }
    #[cfg(windows)]
    {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::Foundation::HANDLE;
        use windows_sys::Win32::Storage::FileSystem::{
            GetFileInformationByHandle, BY_HANDLE_FILE_INFORMATION,
        };
        let _ = metadata;
        let parent_file = home_dir
            .try_clone()
            .map_err(|e| e.to_string())?
            .into_std_file();
        let mut options = fs_at::OpenOptions::default();
        options.read(true).follow(false);
        let file = options
            .open_at(&parent_file, name)
            .map_err(|e| e.to_string())?;
        let mut information = std::mem::MaybeUninit::<BY_HANDLE_FILE_INFORMATION>::uninit();
        let handle: HANDLE = file.as_raw_handle();
        // SAFETY: `file` owns a valid handle for the call, and the Win32 API
        // initializes `information` on success before we read its link count.
        let succeeded = unsafe { GetFileInformationByHandle(handle, information.as_mut_ptr()) };
        if succeeded == 0 {
            return Err(std::io::Error::last_os_error().to_string());
        }
        Ok(unsafe { information.assume_init() }.nNumberOfLinks > 1)
    }
    #[cfg(not(any(unix, windows)))]
    {
        let _ = (home_dir, name, metadata);
        Ok(true)
    }
}

fn validate_database_targets(home: &Path, home_dir: &cap_std::fs::Dir) -> Result<(), String> {
    for name in [
        "agentrouter.db",
        "agentrouter.db-wal",
        "agentrouter.db-shm",
        "agentrouter.db-journal",
    ] {
        match home_dir.symlink_metadata(name) {
            Ok(metadata) => {
                if !metadata.file_type().is_file()
                    || metadata.file_type().is_symlink()
                    || has_multiple_links(home_dir, name, &metadata)?
                {
                    return Err(format!(
                        "unsafe database target: {}",
                        home.join(name).display()
                    ));
                }
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.to_string()),
        }
    }
    Ok(())
}

fn storage_home(home: &Path, home_dir: &cap_std::fs::Dir) -> PathBuf {
    #[cfg(target_os = "linux")]
    {
        use std::os::fd::AsRawFd;
        let _ = home;
        // SQLite opens the database and WAL sidecars by pathname. A proc-fd
        // directory pathname resolves through this pinned directory handle
        // even if the original home path is renamed or replaced concurrently.
        PathBuf::from(format!("/proc/self/fd/{}", home_dir.as_raw_fd()))
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = home_dir;
        home.to_path_buf()
    }
}

/// Force reseeding mirrors Python's backup-before-overwrite behavior for
/// ordinary files. Refuse links before writing because following one could
/// redirect a forced overwrite outside AgentRouter's home.
pub fn init_home_with_force(home: &Path, force: bool) -> Result<Vec<String>, String> {
    let registry = home.join("registry");
    let home_file = open_safe_home(home)?;
    let registry_file = open_directory_child(&home_file, Path::new("registry"))?;
    let home_dir = cap_std::fs::Dir::from_std_file(home_file);
    let registry_dir = cap_std::fs::Dir::from_std_file(registry_file);
    let seeds = [
        (
            home.join("config.yaml"),
            include_str!("../../../agentrouter/seeds/config.yaml"),
            &home_dir,
        ),
        (
            registry.join("providers.yaml"),
            include_str!("../../../agentrouter/seeds/providers.yaml"),
            &registry_dir,
        ),
        (
            registry.join("models.yaml"),
            include_str!("../../../agentrouter/seeds/models.yaml"),
            &registry_dir,
        ),
    ];
    let mut lines = Vec::new();
    for (destination, contents, parent) in seeds {
        let name = Path::new(destination.file_name().ok_or("invalid seed destination")?);
        if force {
            match parent.symlink_metadata(name) {
                Ok(metadata) => {
                    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
                        return Err(format!("unsafe seed target: {}", destination.display()));
                    }
                    let mut backup_name = destination.as_os_str().to_os_string();
                    backup_name.push(".bak");
                    let backup = std::path::PathBuf::from(backup_name);
                    let backup_file_name = backup.file_name().ok_or("invalid backup name")?;
                    let backup_leaf = Path::new(backup_file_name);
                    let mut backup_permissions = None;
                    if let Ok(metadata) = parent.symlink_metadata(backup_leaf) {
                        if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
                            return Err(format!("unsafe backup target: {}", backup.display()));
                        }
                        backup_permissions = Some(metadata.permissions());
                    }
                    let mut options = fs_at::OpenOptions::default();
                    options.read(true).follow(false);
                    let parent_file = parent
                        .try_clone()
                        .map_err(|e| e.to_string())?
                        .into_std_file();
                    let mut source = options
                        .open_at(&parent_file, name)
                        .map_err(|e| e.to_string())?;
                    let source_metadata = source.metadata().map_err(|e| e.to_string())?;
                    if !source_metadata.is_file() || is_link_or_reparse(&source_metadata) {
                        return Err(format!("unsafe seed target: {}", destination.display()));
                    }
                    atomic_replace(
                        parent,
                        backup_leaf,
                        &mut source,
                        backup_permissions.as_ref(),
                    )?;
                    lines.push(format!(
                        "Backed up {} -> {}",
                        destination.display(),
                        backup.display()
                    ));
                    atomic_replace(
                        parent,
                        name,
                        &mut contents.as_bytes(),
                        Some(&metadata.permissions()),
                    )?;
                    lines.push(format!("Created {}", destination.display()));
                    continue;
                }
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                Err(error) => return Err(error.to_string()),
            }
        }
        let mut options = cap_std::fs::OpenOptions::new();
        options.write(true).create_new(true);
        match parent.open_with(name, &options) {
            Ok(mut file) => {
                file.write_all(contents.as_bytes())
                    .map_err(|e| e.to_string())?;
                lines.push(format!("Created {}", destination.display()));
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
                lines.push(format!(
                    "exists, skipped: {} (use --force to overwrite)",
                    destination.display()
                ));
            }
            Err(error) => return Err(error.to_string()),
        }
    }
    validate_database_targets(home, &home_dir)?;
    agentrouter_storage::connect(&storage_home(home, &home_dir)).map_err(|e| e.to_string())?;
    lines.push(format!(
        "Initialized {}",
        home.join("agentrouter.db").display()
    ));
    lines.push("Ready. Try: agentrouter route \"your task here\"".to_string());
    Ok(lines)
}

fn dirs_home() -> std::path::PathBuf {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| Path::new(".").to_path_buf())
}

#[cfg(test)]
mod tests {
    #[cfg(target_os = "linux")]
    #[test]
    fn sqlite_init_uses_pinned_home_after_path_swap() {
        use std::os::unix::fs::symlink;
        let root = std::env::temp_dir().join(format!(
            "agentrouter-pinned-home-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let home = root.join("home");
        let moved = root.join("moved");
        let outside = root.join("outside");
        std::fs::create_dir_all(&home).unwrap();
        std::fs::create_dir(&outside).unwrap();
        let pinned = cap_std::fs::Dir::from_std_file(super::open_safe_home(&home).unwrap());
        std::fs::rename(&home, &moved).unwrap();
        symlink(&outside, &home).unwrap();
        let storage_home = super::storage_home(&home, &pinned);
        let conn = agentrouter_storage::connect(&storage_home).unwrap();
        conn.execute("CREATE TABLE pinned_test (id INTEGER)", [])
            .unwrap();
        assert!(moved.join("agentrouter.db").exists());
        assert!(moved.join("agentrouter.db-wal").exists());
        assert!(moved.join("agentrouter.db-shm").exists());
        assert!(!outside.join("agentrouter.db").exists());
        assert!(!outside.join("agentrouter.db-wal").exists());
        assert!(!outside.join("agentrouter.db-shm").exists());
        drop(conn);
        std::fs::remove_file(&home).unwrap();
        std::fs::remove_dir_all(root).unwrap();
    }

    use super::*;
    use agentrouter_core::{ContextBand, OutputType, TaskType};

    fn cls(risk: Level, approval: ApprovalLevel) -> Classification {
        Classification {
            task_type: TaskType::Coding,
            complexity: Level::Medium,
            risk,
            context_tokens: 2000,
            context_band: ContextBand::Small,
            output_type: OutputType::Code,
            tool_needs: vec![],
            approval_level: approval,
            confidence: 1.0,
            needs_clarification: false,
            alternative_task_type: None,
            ambiguity_reason: None,
        }
    }

    #[test]
    fn gates_high_risk_never_auto_executes() {
        let g = gates_for(&cls(Level::High, ApprovalLevel::Auto));
        assert_eq!(g["auto_execute_allowed"], false);
        assert_eq!(g["checklist"].as_array().unwrap().len(), 5);
    }

    #[test]
    fn gates_low_risk_auto_allows_execution() {
        let g = gates_for(&cls(Level::Low, ApprovalLevel::Auto));
        assert_eq!(g["auto_execute_allowed"], true);
        assert_eq!(g["checklist"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn prompt_includes_stop_line_when_approval_required() {
        let c = cls(Level::High, ApprovalLevel::HumanApprovalRequired);
        let checklist = gates_for(&c)["checklist"].clone();
        let p = generate_prompt(
            "do it",
            "anthropic/claude",
            &c,
            checklist.as_array().unwrap(),
        );
        assert!(p.contains("STOP before any irreversible action"));
    }

    #[test]
    fn prompt_from_decision_reuses_or_regenerates() {
        let c = cls(Level::Low, ApprovalLevel::Auto);
        let gates = gates_for(&c);
        let payload = json!({
            "task": "do it",
            "classification": c,
            "gates": gates,
            "prompt": "saved prompt",
        });
        assert_eq!(
            prompt_from_decision(&payload, None).unwrap(),
            "saved prompt"
        );
        let regenerated = prompt_from_decision(&payload, Some("other/tool")).unwrap();
        assert!(regenerated.contains("Target tool: other/tool"));
        assert!(regenerated.contains("## Task\ndo it"));
        assert!(prompt_from_decision(&json!({}), Some("other/tool")).is_err());
    }

    #[test]
    fn apply_policy_caps_pricing_tier() {
        use agentrouter_registry::ModelEntry;
        let make = |tier: &str| -> ModelEntry {
            let yaml = format!(
                "provider: p\nmodel_id: m\ncontext_window: 1000\nmax_output_tokens: 100\npricing_tier: {tier}\nlatency_tier: fast\nability: {{coding: 5, reasoning: 5, writing: 5}}\ntool_support: []\nvision_support: false\ndeprecation_status: active\n"
            );
            serde_yaml::from_str(&yaml).unwrap()
        };
        let models = vec![make("free"), make("frontier")];
        let kept = apply_policy(models, Some("low")).unwrap();
        assert_eq!(kept.len(), 1);
    }

    #[test]
    fn apply_policy_rejects_unknown_tier() {
        let err = apply_policy(vec![], Some("made-up")).unwrap_err();
        assert!(err.contains("Config error"));
    }

    #[test]
    fn apply_policy_none_is_identity() {
        let kept = apply_policy(vec![], None).unwrap();
        assert!(kept.is_empty());
    }
}
