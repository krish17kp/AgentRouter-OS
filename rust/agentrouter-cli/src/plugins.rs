//! Plugin manifest metadata and portable path validation.
//!
//! This is the first Rust slice of `agentrouter.plugins`. It deliberately ports
//! the trust boundary before filesystem mutation: plugin names and manifest
//! paths are checked with the same cross-platform rules as Python.

use std::fs::File;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::SystemTime;

use sha2::Digest;

const CLAUDE_SOURCE: &str = "claude-code/agentrouter/SKILL.md";
const CODEX_SOURCE: &str = "codex/AGENTS.md";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PluginFile {
    pub src: &'static str,
    pub dest: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PluginSpec {
    pub name: &'static str,
    pub description: &'static str,
    pub files: &'static [PluginFile],
    pub home_subdir: &'static str,
    pub cleanup_dirs: &'static [&'static str],
}

const CLAUDE_FILES: &[PluginFile] = &[PluginFile {
    src: "claude-code/agentrouter/SKILL.md",
    dest: "skills/agentrouter/SKILL.md",
}];
const CODEX_FILES: &[PluginFile] = &[PluginFile {
    src: "codex/AGENTS.md",
    dest: "AGENTS.md",
}];
const CLAUDE_CLEANUP: &[&str] = &["skills/agentrouter"];
const NO_CLEANUP: &[&str] = &[];
const PLUGINS: &[PluginSpec] = &[
    PluginSpec {
        name: "claude-code",
        description: "AgentRouter routing skill for Claude Code (~/.claude/skills/agentrouter/).",
        files: CLAUDE_FILES,
        home_subdir: ".claude",
        cleanup_dirs: CLAUDE_CLEANUP,
    },
    PluginSpec {
        name: "codex",
        description: "AgentRouter AGENTS.md guidance for Codex (~/.codex/AGENTS.md).",
        files: CODEX_FILES,
        home_subdir: ".codex",
        cleanup_dirs: NO_CLEANUP,
    },
];

/// Return the stable bundled plugin inventory in Python insertion order.
pub fn known_plugins() -> &'static [PluginSpec] {
    PLUGINS
}

/// Resolve a bundled plugin name with bounded, single-line diagnostics.
pub fn get_plugin(name: &str) -> Result<&'static PluginSpec, String> {
    PLUGINS
        .iter()
        .find(|plugin| plugin.name == name)
        .ok_or_else(|| {
            format!(
                "unknown plugin '{}'. Known: {}",
                crate::observability::safe_echo_default(name),
                PLUGINS
                    .iter()
                    .map(|plugin| plugin.name)
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        })
}

/// Validate a portable relative path and return its exact path components.
///
/// Both slash styles are treated as separators even on Unix. This prevents a
/// manifest accepted on one platform from becoming traversal when installed on
/// another. Empty, dot, dot-dot, drive, UNC, control, forbidden, trailing-dot/
/// space, and Windows device-name components are rejected.
pub fn safe_relative(value: &str, label: &str) -> Result<Vec<String>, String> {
    let normalized = value.replace('\\', "/");
    let parts = normalized.split('/').collect::<Vec<_>>();
    let invalid_part = parts.iter().any(|part| {
        part.is_empty()
            || *part == "."
            || *part == ".."
            || part.ends_with(' ')
            || part.ends_with('.')
            || part
                .chars()
                .any(|character| character <= '\u{1f}' || "<>:\"|?*".contains(character))
            || is_windows_reserved(part)
    });
    let drive_prefixed = normalized.as_bytes().get(1) == Some(&b':')
        && normalized
            .as_bytes()
            .first()
            .is_some_and(u8::is_ascii_alphabetic);
    if value.is_empty()
        || value.contains('\0')
        || invalid_part
        || Path::new(&normalized).is_absolute()
        || normalized.starts_with("//")
        || drive_prefixed
    {
        return Err(format!(
            "unsafe relative path for {label}: {}",
            python_string_repr(value)
        ));
    }
    Ok(parts.into_iter().map(str::to_owned).collect())
}

fn is_windows_reserved(part: &str) -> bool {
    let basename = part
        .split_once('.')
        .map_or(part, |(basename, _)| basename)
        .trim_end_matches(&[' ', '.'][..])
        .to_ascii_uppercase();
    matches!(basename.as_str(), "CON" | "PRN" | "AUX" | "NUL")
        || ["COM", "LPT"].iter().any(|prefix| {
            basename.strip_prefix(prefix).is_some_and(|suffix| {
                suffix.len() == 1 && suffix.as_bytes()[0].is_ascii_digit() && suffix != "0"
            })
        })
}

fn python_string_repr(value: &str) -> String {
    // Rust's debug representation is deterministic and preserves control
    // characters as escapes; it intentionally avoids emitting raw CR/LF.
    format!("{value:?}")
}

/// Resolve the destination root using injected environment values for tests.
pub fn dest_root(
    plugin: &PluginSpec,
    override_root: Option<&Path>,
    home: Option<&Path>,
) -> Result<PathBuf, String> {
    if let Some(root) = override_root.filter(|path| !path.as_os_str().is_empty()) {
        let name = safe_relative(plugin.name, "plugin name")?;
        if name.len() != 1 {
            return Err(format!(
                "unsafe relative path for plugin name: {}",
                python_string_repr(plugin.name)
            ));
        }
        return Ok(root.join(&name[0]));
    }
    let home = home.ok_or_else(|| "user home directory is unavailable".to_owned())?;
    let parts = safe_relative(plugin.home_subdir, "plugin home")?;
    Ok(parts
        .iter()
        .fold(home.to_path_buf(), |path, part| path.join(part)))
}

fn plugin_path(root: &Path, relative: &str) -> PathBuf {
    relative
        .replace('\\', "/")
        .split('/')
        .fold(root.to_path_buf(), |path, component| path.join(component))
}

/// Read-only install-state summary for `agentrouter plugin list`.
///
/// A destination is considered installed when its path exists, matching
/// Python's display summary. A linked or uninspectable path is `blocked` so a
/// status command never follows a link or hides a safety finding.
pub fn status(plugin: &PluginSpec, root: &Path) -> &'static str {
    let metadata = match std::fs::symlink_metadata(root) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return "not-installed",
        Err(_) => return "blocked",
    };
    if super::is_link_or_reparse(&metadata) || !metadata.is_dir() {
        return "blocked";
    }
    let root_file = match super::open_safe_home(root) {
        Ok(file) => file,
        Err(_) => return "blocked",
    };
    let root_dir = cap_std::fs::Dir::from_std_file(root_file);
    let mut present = 0;
    for file in plugin.files {
        match safe_path_exists(&root_dir, file.dest) {
            Ok(true) => present += 1,
            Ok(false) => {}
            Err(_) => return "blocked",
        }
    }
    if present == plugin.files.len() {
        "installed"
    } else if present > 0 {
        "partial"
    } else {
        "not-installed"
    }
}

/// Diagnose plugin installation state without changing host files.
pub fn diagnose(plugin: &PluginSpec, root: &Path) -> Vec<serde_json::Value> {
    let mut findings = Vec::new();
    let host_parent_exists = match root.parent().map(path_entry_exists) {
        Some(Ok(exists)) => exists,
        Some(Err(_)) | None => {
            findings.push(diagnose_failure(plugin));
            return findings;
        }
    };
    let root_exists = match path_entry_exists(root) {
        Ok(exists) => exists,
        Err(_) => {
            findings.push(diagnose_failure(plugin));
            return findings;
        }
    };
    if !host_parent_exists && !root_exists {
        findings.push(serde_json::json!({
            "plugin": plugin.name,
            "check": "host-root",
            "status": "attention",
            "summary": format!("the host directory {} does not exist yet", root.display()),
            "remedy": format!("it is created on install: agentrouter plugin install {}", plugin.name),
        }));
    }

    let transaction = format!(".agentrouter-state/{}.txn.json", plugin.name);
    match relative_entry_exists(root, &transaction) {
        Ok(true) => findings.push(serde_json::json!({
            "plugin": plugin.name,
            "check": "transaction",
            "status": "attention",
            "summary": "a previous install or uninstall did not finish",
            "remedy": format!(
                "recover with the Python CLI: python -m agentrouter plugin install {}",
                plugin.name
            ),
        })),
        Ok(false) => {}
        Err(_) => {
            findings.push(diagnose_failure(plugin));
            return findings;
        }
    }

    let state_relative = format!(".agentrouter-state/{}.json", plugin.name);
    let state_exists = match relative_entry_exists(root, &state_relative) {
        Ok(exists) => exists,
        Err(_) => {
            findings.push(diagnose_failure(plugin));
            return findings;
        }
    };
    let state = match read_state(root, plugin) {
        Ok(state) => state,
        Err(_) if state_exists => {
            let state_path = root
                .join(".agentrouter-state")
                .join(format!("{}.json", plugin.name));
            findings.push(serde_json::json!({
                "plugin": plugin.name,
                "check": "ownership",
                "status": "blocked",
                "summary": "the ownership record is unusable (PluginError)",
                "remedy": format!(
                    "AgentRouter will not delete files it cannot prove it owns. Remove {} only if you are content to manage these files by hand afterwards.",
                    state_path.display()
                ),
            }));
            return findings;
        }
        Err(_) => {
            findings.push(diagnose_failure(plugin));
            return findings;
        }
    };

    for file in plugin.files {
        if let Err(error) = check_link_components(root, file.dest) {
            findings.push(serde_json::json!({
                "plugin": plugin.name,
                "check": "destination",
                "status": "blocked",
                "summary": format!("cannot inspect the destination: {error}"),
                "remedy": "resolve the path above, then re-run this check",
            }));
            return findings;
        }
    }

    for file in plugin.files {
        let destination = plugin_path(root, file.dest);
        let state_entry = state
            .as_ref()
            .and_then(|loaded| loaded.value.get("files"))
            .and_then(serde_json::Value::as_object)
            .and_then(|files| files.get(file.dest));
        let expected = match bundled_contents(file.src) {
            Some(bytes) => bytes,
            None => {
                findings.push(diagnose_failure(plugin));
                return findings;
            }
        };
        let expected_digest = format!("{:x}", sha2::Sha256::digest(expected));
        let action = match read_relative_file(root, file.dest) {
            Ok(None) => "create",
            Ok(Some(actual)) => {
                let actual_digest = format!("{:x}", sha2::Sha256::digest(&actual.bytes));
                let owned = state_entry.is_some_and(|entry| {
                    matches!(
                        entry.get("disposition").and_then(serde_json::Value::as_str),
                        Some("created" | "replaced")
                    ) && entry
                        .get("installed_sha256")
                        .and_then(serde_json::Value::as_str)
                        == Some(actual_digest.as_str())
                        && entry.get("installed_identity")
                            == Some(&serde_json::json!([actual.identity.0, actual.identity.1]))
                });
                if owned && actual_digest == expected_digest {
                    "skip (identical, managed)"
                } else if actual.bytes == expected {
                    "adopt identical legacy installation (managed)"
                } else {
                    "overwrite (backup first)"
                }
            }
            Err(_) => "blocked (not a safe regular file)",
        };
        let (severity, summary, remedy) = diagnosis_for_action(action, plugin.name);
        findings.push(serde_json::json!({
            "plugin": plugin.name,
            "check": "file",
            "status": severity,
            "dest": destination,
            "summary": summary,
            "remedy": remedy,
        }));
    }
    findings
}

/// Preview plugin installation changes without modifying host files.
pub fn plan(
    plugin: &PluginSpec,
    root: &Path,
    adopt_identical: bool,
) -> Result<Vec<serde_json::Value>, String> {
    let state = read_state(root, plugin)?.map(|loaded| loaded.value);
    let mut plan = Vec::new();
    for file in plugin.files {
        check_link_components(root, file.dest)?;
        let destination = plugin_path(root, file.dest);
        let expected = bundled_contents(file.src)
            .ok_or_else(|| format!("packaged plugin source is missing: {}", file.src))?;
        let expected_digest = format!("{:x}", sha2::Sha256::digest(expected));
        let state_entry = state
            .as_ref()
            .and_then(|value| value.get("files"))
            .and_then(serde_json::Value::as_object)
            .and_then(|files| files.get(file.dest));
        let action = match read_relative_file(root, file.dest) {
            Ok(None) => "create",
            Ok(Some(actual)) => {
                let actual_digest = format!("{:x}", sha2::Sha256::digest(&actual.bytes));
                let managed = state_entry.is_some_and(|entry| {
                    matches!(
                        entry.get("disposition").and_then(serde_json::Value::as_str),
                        Some("created" | "replaced")
                    ) && entry
                        .get("installed_sha256")
                        .and_then(serde_json::Value::as_str)
                        == Some(actual_digest.as_str())
                        && entry.get("installed_identity")
                            == Some(&serde_json::json!([actual.identity.0, actual.identity.1]))
                });
                if managed && actual_digest == expected_digest {
                    "skip (identical, managed)"
                } else if actual.bytes == expected && adopt_identical {
                    "adopt identical legacy installation (managed)"
                } else if actual.bytes == expected {
                    "record pre-existing (preserved on uninstall)"
                } else {
                    "overwrite (backup first)"
                }
            }
            Err(_) => "blocked (not a safe regular file)",
        };
        plan.push(serde_json::json!({
            "kind": "file",
            "dest": destination,
            "action": action,
        }));
    }
    Ok(plan)
}

/// Install only missing or byte-identical files. Destructive replacement is
/// intentionally rejected until the journaled backup and recovery protocol is
/// available in Rust.
pub fn install(
    plugin: &PluginSpec,
    root: &Path,
    force: bool,
    adopt_identical: bool,
) -> Result<Vec<serde_json::Value>, String> {
    if force {
        return Err("forced plugin replacement is not migrated yet; use the Python CLI".to_owned());
    }
    for file in plugin.files {
        bundled_contents(file.src)
            .ok_or_else(|| format!("packaged plugin source is missing: {}", file.src))?;
        check_link_components(root, file.dest)?;
        check_link_components(root, &format!("{}.agentrouter-bak", file.dest))?;
    }
    let transaction = format!(".agentrouter-state/{}.txn.json", plugin.name);
    if relative_entry_exists(root, &transaction)? {
        return Err(
            "an interrupted plugin transaction exists; use the Python CLI to recover it".to_owned(),
        );
    }

    let loaded = read_state(root, plugin)?;
    let mut state_sha = loaded.as_ref().map(|loaded| loaded.sha256.clone());
    let mut state = loaded
        .map(|loaded| loaded.value)
        .unwrap_or_else(|| empty_state(plugin));
    let known_paths = plugin
        .files
        .iter()
        .map(|file| file.dest)
        .collect::<std::collections::HashSet<_>>();
    if let Some(files) = state.get("files").and_then(serde_json::Value::as_object) {
        let historical = files
            .keys()
            .filter(|path| !known_paths.contains(path.as_str()))
            .cloned()
            .collect::<Vec<_>>();
        if !historical.is_empty() {
            return Err(format!(
                "plugin registry paths changed; use the Python CLI to safely handle historical paths: {}",
                historical.join(", ")
            ));
        }
    }

    let root_file = super::open_safe_home(root)?;
    let root_dir = cap_std::fs::Dir::from_std_file(root_file);
    let mut results = Vec::new();
    for relative in plugin.cleanup_dirs {
        let existing = existing_relative_directory(&root_dir, relative)?;
        if let Some(directory) = existing {
            let identity = directory_identity(&directory)?;
            if let Some(previous) = state
                .get("directories")
                .and_then(serde_json::Value::as_object)
                .and_then(|directories| directories.get(*relative))
                .and_then(|entry| entry.get("identity"))
            {
                if previous != &identity {
                    return Err(format!(
                        "managed plugin directory identity changed: {}",
                        plugin_path(root, relative).display()
                    ));
                }
            }
        } else {
            let (directory, created) = ensure_relative_directory(&root_dir, relative)?;
            if !created {
                return Err(format!(
                    "plugin cleanup directory appeared concurrently; refusing to claim ownership: {}",
                    plugin_path(root, relative).display()
                ));
            }
            let identity = directory_identity(&directory)?;
            state["directories"][*relative] = serde_json::json!({"identity": identity});
            let saved = save_state(root, &root_dir, plugin, &mut state, state_sha.as_deref())?;
            state_sha = Some(saved.sha256);
        }
    }

    for file in plugin.files {
        let destination = plugin_path(root, file.dest);
        let expected = bundled_contents(file.src)
            .ok_or_else(|| format!("packaged plugin source is missing: {}", file.src))?;
        let digest = format!("{:x}", sha2::Sha256::digest(expected));
        let prior = state
            .get("files")
            .and_then(serde_json::Value::as_object)
            .and_then(|files| files.get(file.dest))
            .cloned();
        let actual = read_relative_file(root, file.dest)?;
        if let Some(entry) = prior.as_ref().filter(|entry| {
            matches!(
                entry.get("disposition").and_then(serde_json::Value::as_str),
                Some("created" | "replaced")
            )
        }) {
            let matches = actual.as_ref().is_some_and(|actual| {
                entry
                    .get("installed_sha256")
                    .and_then(serde_json::Value::as_str)
                    == Some(format!("{:x}", sha2::Sha256::digest(&actual.bytes)).as_str())
                    && entry.get("installed_identity")
                        == Some(&serde_json::json!([actual.identity.0, actual.identity.1]))
            });
            if !matches {
                return Err(format!(
                    "{} changed after AgentRouter installed it; refusing to overwrite the user edit.",
                    destination.display()
                ));
            }
            if actual
                .as_ref()
                .is_some_and(|actual| actual.bytes == expected)
                && entry
                    .get("installed_sha256")
                    .and_then(serde_json::Value::as_str)
                    == Some(digest.as_str())
            {
                results.push(plugin_result(&destination, "skipped (identical, managed)"));
                continue;
            }
            return Err(
                "managed plugin upgrades require the Rust transaction recovery protocol; use the Python CLI"
                    .to_owned(),
            );
        }

        if let Some(actual) = actual {
            if actual.bytes != expected {
                return Err(format!(
                    "{} exists and differs; re-run with --force to back it up and replace.",
                    destination.display()
                ));
            }
            let disposition = if adopt_identical {
                "created"
            } else {
                "preexisting"
            };
            state["files"][file.dest] = serde_json::json!({
                "disposition": disposition,
                "installed_sha256": digest,
                "installed_identity": [actual.identity.0, actual.identity.1],
                "backup": null,
            });
            save_state(root, &root_dir, plugin, &mut state, state_sha.as_deref())?;
            state_sha = read_state(root, plugin)?.map(|loaded| loaded.sha256);
            results.push(plugin_result(
                &destination,
                if adopt_identical {
                    "adopted identical legacy installation (managed)"
                } else {
                    "skipped (identical pre-existing file; will be preserved)"
                },
            ));
            continue;
        }

        let (parent, name) = open_relative_parent(&root_dir, file.dest, true)?
            .ok_or_else(|| "plugin destination parent is unavailable".to_owned())?;
        let installed = create_no_clobber(&parent, &name, &destination, expected, 0o644)?;
        state["files"][file.dest] = serde_json::json!({
            "disposition": "created",
            "installed_sha256": digest,
            "installed_identity": [installed.identity.0, installed.identity.1],
            "backup": null,
        });
        match save_state(root, &root_dir, plugin, &mut state, state_sha.as_deref()) {
            Ok(saved) => state_sha = Some(saved.sha256),
            Err(error) => {
                let rollback =
                    remove_exact_file(root, &root_dir, file.dest, &digest, installed.identity);
                return match rollback {
                    Ok(true) => Err(error),
                    Ok(false) => Err(format!(
                        "{error}; the destination changed concurrently and was preserved"
                    )),
                    Err(rollback_error) => Err(format!(
                        "{error}; install rollback was incomplete: {rollback_error}"
                    )),
                };
            }
        }
        results.push(plugin_result(&destination, "created"));
    }
    Ok(results)
}

/// Remove only files whose ownership record still proves that AgentRouter
/// created them. User edits, unmanaged files, unsafe paths, and ambiguous
/// backups are kept in place for Python-compatible recovery.
pub fn uninstall(plugin: &PluginSpec, root: &Path) -> Result<Vec<serde_json::Value>, String> {
    let transaction = format!(".agentrouter-state/{}.txn.json", plugin.name);
    if relative_entry_exists(root, &transaction)? {
        return Err(
            "an interrupted plugin transaction exists; use the Python CLI to recover it".to_owned(),
        );
    }

    let loaded = read_state(root, plugin)?;
    let mut state_sha = loaded.as_ref().map(|loaded| loaded.sha256.clone());
    let mut state = loaded
        .map(|loaded| loaded.value)
        .unwrap_or_else(|| empty_state(plugin));

    // Validate every path in the ownership record and current manifest before
    // the first mutation, including historical paths from older manifests.
    let mut destinations = state
        .get("files")
        .and_then(serde_json::Value::as_object)
        .map(|files| files.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    for file in plugin.files {
        if !destinations.iter().any(|relative| relative == file.dest) {
            destinations.push(file.dest.to_owned());
        }
    }
    for relative in &destinations {
        check_link_components(root, relative)?;
        if let Some(entry) = state
            .get("files")
            .and_then(serde_json::Value::as_object)
            .and_then(|files| files.get(relative))
        {
            if let Some(backup) = entry.get("backup").and_then(serde_json::Value::as_str) {
                check_link_components(root, backup)?;
            }
        }
    }
    let mut cleanup_directories = state
        .get("directories")
        .and_then(serde_json::Value::as_object)
        .map(|directories| directories.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    for relative in plugin.cleanup_dirs {
        if !cleanup_directories
            .iter()
            .any(|existing| existing == relative)
        {
            cleanup_directories.push((*relative).to_owned());
        }
    }
    for relative in &cleanup_directories {
        check_link_components(root, relative)?;
    }

    let root_file = match std::fs::symlink_metadata(root) {
        Ok(metadata) if !super::is_link_or_reparse(&metadata) && metadata.is_dir() => {
            super::open_safe_home(root)?
        }
        Ok(_) => return Err("plugin destination root is not a safe directory".to_owned()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            let mut results = destinations
                .iter()
                .map(|relative| plugin_result(&plugin_path(root, relative), "absent"))
                .collect::<Vec<_>>();
            results.extend(cleanup_directories.iter().map(|relative| {
                serde_json::json!({
                    "kind": "directory",
                    "dest": plugin_path(root, relative).to_string_lossy(),
                    "result": "absent",
                })
            }));
            return Ok(results);
        }
        Err(error) => return Err(format!("could not inspect plugin root: {error}")),
    };
    let root_dir = cap_std::fs::Dir::from_std_file(root_file);
    let mut results = Vec::new();

    for relative in destinations {
        let entry = state
            .get("files")
            .and_then(serde_json::Value::as_object)
            .and_then(|files| files.get(&relative))
            .cloned();
        let destination = plugin_path(root, &relative);
        let result = match entry {
            None => if relative_entry_exists(root, &relative)? {
                "preserved (unmanaged)"
            } else {
                "absent"
            }
            .to_owned(),
            Some(entry) if entry["disposition"] == "preexisting" => {
                state["files"]
                    .as_object_mut()
                    .expect("validated ownership state has files")
                    .remove(&relative);
                "preserved (pre-existing)".to_owned()
            }
            Some(entry) => {
                let backup_rel = entry
                    .get("backup")
                    .and_then(serde_json::Value::as_str)
                    .map(str::to_owned);
                let backup = backup_rel.as_deref();
                if let Some(backup) = backup {
                    let backup_exists = relative_entry_exists(root, backup)?;
                    let destination_file =
                        verified_file_if_readable_with_hardlinks(root, &relative, true);
                    if destination_file
                        .as_ref()
                        .is_some_and(|file| file_matches_backup(file, &entry))
                    {
                        if !backup_exists {
                            state["files"]
                                .as_object_mut()
                                .expect("validated ownership state has files")
                                .remove(&relative);
                            "recovered completed backup restoration".to_owned()
                        } else {
                            let backup_file =
                                verified_file_if_readable_with_hardlinks(root, backup, true);
                            if backup_file.as_ref().is_some_and(|file| {
                                file_matches_backup(file, &entry)
                                    && Some(file.identity)
                                        == destination_file.as_ref().map(|file| file.identity)
                            }) {
                                discard_restored_backup(root, &root_dir, backup, &entry)?;
                                state["files"]
                                    .as_object_mut()
                                    .expect("validated ownership state has files")
                                    .remove(&relative);
                                "recovered completed backup restoration".to_owned()
                            } else {
                                "preserved (backup missing or changed; ownership is ambiguous)"
                                    .to_owned()
                            }
                        }
                    } else if !backup_exists
                        || !verified_file_if_readable(root, backup)
                            .as_ref()
                            .is_some_and(|file| file_matches_backup(file, &entry))
                    {
                        "preserved (backup missing or changed; ownership is ambiguous)".to_owned()
                    } else {
                        let (result, clear_entry) =
                            uninstall_managed_file(root, &root_dir, &relative, backup, &entry)?;
                        if clear_entry {
                            state["files"]
                                .as_object_mut()
                                .expect("validated ownership state has files")
                                .remove(&relative);
                        }
                        result
                    }
                } else {
                    let (result, clear_entry) =
                        uninstall_managed_file(root, &root_dir, &relative, "", &entry)?;
                    if clear_entry {
                        state["files"]
                            .as_object_mut()
                            .expect("validated ownership state has files")
                            .remove(&relative);
                    }
                    result
                }
            }
        };
        results.push(serde_json::json!({
            "kind": "file",
            "dest": destination.to_string_lossy(),
            "result": result,
        }));
        match persist_uninstall_state(root, &root_dir, plugin, &mut state, state_sha.as_deref())? {
            Some(saved) => state_sha = Some(saved.sha256),
            None => state_sha = None,
        }
    }

    for relative in cleanup_directories {
        let directory = plugin_path(root, &relative);
        let identity = state
            .get("directories")
            .and_then(serde_json::Value::as_object)
            .and_then(|directories| directories.get(&relative))
            .and_then(|entry| entry.get("identity"))
            .cloned();
        let result = match identity {
            None => {
                if relative_entry_exists(root, &relative)? {
                    "preserved (unmanaged directory)".to_owned()
                } else {
                    "absent".to_owned()
                }
            }
            Some(identity) => {
                let identity_values = identity.as_array().and_then(|values| {
                    Some((
                        python_integer_to_u64(values.first()?)?,
                        python_integer_to_u64(values.get(1)?)?,
                    ))
                });
                if let Some(identity_values) = identity_values {
                    let result =
                        remove_owned_empty_directory(root, &root_dir, &relative, identity_values)?;
                    if matches!(result.as_str(), "absent" | "removed (empty directory)") {
                        state["directories"]
                            .as_object_mut()
                            .expect("validated ownership state has directories")
                            .remove(&relative);
                    }
                    result
                } else {
                    "preserved (directory identity changed)".to_owned()
                }
            }
        };
        results.push(serde_json::json!({
            "kind": "directory",
            "dest": directory.to_string_lossy(),
            "result": result,
        }));
        match persist_uninstall_state(root, &root_dir, plugin, &mut state, state_sha.as_deref())? {
            Some(saved) => state_sha = Some(saved.sha256),
            None => state_sha = None,
        }
    }
    Ok(results)
}

fn python_integer_to_u64(value: &serde_json::Value) -> Option<u64> {
    if value.is_boolean() {
        return Some(u64::from(value.as_bool()?));
    }
    value.as_u64()
}

fn verified_file_if_readable(root: &Path, relative: &str) -> Option<VerifiedFile> {
    read_relative_file(root, relative).ok().flatten()
}

fn verified_file_if_readable_with_hardlinks(
    root: &Path,
    relative: &str,
    allow_hardlinks: bool,
) -> Option<VerifiedFile> {
    let root_file = crate::open_safe_home(root).ok()?;
    let root_dir = cap_std::fs::Dir::from_std_file(root_file);
    let (parent, name) = open_relative_parent(&root_dir, relative, false).ok()??;
    read_verified_file_at_with_hardlinks(
        &parent,
        &name,
        &plugin_path(root, relative),
        allow_hardlinks,
    )
    .ok()
    .flatten()
}

fn file_matches_backup(file: &VerifiedFile, entry: &serde_json::Value) -> bool {
    entry
        .get("backup_sha256")
        .and_then(serde_json::Value::as_str)
        == Some(format!("{:x}", sha2::Sha256::digest(&file.bytes)).as_str())
        && entry.get("backup_identity")
            == Some(&serde_json::json!([file.identity.0, file.identity.1]))
        && entry.get("backup_mode").and_then(python_integer_to_u64) == Some(u64::from(file.mode))
}

fn file_matches_installed(file: &VerifiedFile, entry: &serde_json::Value) -> bool {
    entry
        .get("installed_sha256")
        .and_then(serde_json::Value::as_str)
        == Some(format!("{:x}", sha2::Sha256::digest(&file.bytes)).as_str())
        && entry.get("installed_identity")
            == Some(&serde_json::json!([file.identity.0, file.identity.1]))
}

fn uninstall_managed_file(
    root: &Path,
    root_dir: &cap_std::fs::Dir,
    relative: &str,
    backup: &str,
    entry: &serde_json::Value,
) -> Result<(String, bool), String> {
    let backup_present = !backup.is_empty();
    let destination_exists = relative_entry_exists(root, relative)?;
    let destination_file = verified_file_if_readable(root, relative);
    if !destination_exists {
        if !backup_present {
            return Ok(("absent".to_owned(), true));
        }
        restore_backup(root, root_dir, backup, relative, entry)?;
        return Ok(("restored backup (managed file was absent)".to_owned(), true));
    }
    if !destination_file
        .as_ref()
        .is_some_and(|file| file_matches_installed(file, entry))
    {
        let suffix = if backup_present {
            "; backup retained"
        } else {
            ""
        };
        return Ok((
            format!("preserved (not the unchanged managed file){suffix}"),
            false,
        ));
    }

    let installed_digest = entry
        .get("installed_sha256")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| "plugin ownership state lacks an installed digest".to_owned())?;
    let installed_identity = destination_file
        .as_ref()
        .expect("matched installed file exists")
        .identity;
    let Some(staged) = stage_exact_file(
        root,
        root_dir,
        relative,
        installed_digest,
        Some(installed_identity),
        "managed plugin file",
    )?
    else {
        return Ok(("preserved (changed concurrently)".to_owned(), false));
    };
    if backup_present {
        match restore_backup(root, root_dir, backup, relative, entry) {
            Ok(()) => {
                if let Err(error) = remove_staged_file_exact(&staged, "managed plugin file") {
                    return Ok((
                        format!(
                            "removed (restored backup; managed staging retained at {}: {error})",
                            staged.path.display()
                        ),
                        true,
                    ));
                }
                Ok(("removed (restored backup)".to_owned(), true))
            }
            Err(error) => {
                if !relative_entry_exists(root, relative)? {
                    restore_staged_file(&staged)?;
                }
                Err(error)
            }
        }
    } else {
        if let Err(error) = remove_staged_file_exact(&staged, "managed plugin file") {
            return match restore_staged_file(&staged) {
                Ok(()) => Err(format!("could not remove managed plugin file: {error}")),
                Err(restore_error) => Err(format!(
                    "could not remove managed plugin file: {error}; {restore_error}"
                )),
            };
        }
        Ok(("removed".to_owned(), true))
    }
}

#[derive(Debug)]
struct StagedPluginFile {
    parent: cap_std::fs::Dir,
    name: String,
    destination_name: String,
    path: PathBuf,
    identity: (u64, u64),
    digest: String,
    allow_hardlinks: bool,
}

fn staged_name() -> Result<String, String> {
    let mut nonce = [0_u8; 16];
    getrandom::getrandom(&mut nonce)
        .map_err(|error| format!("could not generate a private plugin staging name: {error}"))?;
    let mut name = String::from(".agentrouter-remove-");
    for byte in nonce {
        use std::fmt::Write as _;
        write!(&mut name, "{byte:02x}").expect("writing to a string cannot fail");
    }
    Ok(name)
}

fn unique_staged_name(parent: &cap_std::fs::Dir) -> Result<String, String> {
    for _ in 0..16 {
        let name = staged_name()?;
        match parent.symlink_metadata(&name) {
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(name),
            Ok(_) => continue,
            Err(error) => return Err(format!("could not inspect plugin staging path: {error}")),
        }
    }
    Err("could not allocate a unique plugin staging path".to_owned())
}

fn sibling_directory(relative: &str) -> &str {
    relative.rsplit_once('/').map_or("", |(parent, _)| parent)
}

fn rename_sibling_no_replace(
    root: &Path,
    parent_relative: &str,
    parent: &cap_std::fs::Dir,
    from: &str,
    to: &str,
) -> std::io::Result<()> {
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    {
        let _ = (root, parent_relative);
        let parent_file = parent.try_clone()?.into_std_file();
        rustix::fs::renameat_with(
            &parent_file,
            from,
            &parent_file,
            to,
            rustix::fs::RenameFlags::NOREPLACE,
        )
        .map_err(std::io::Error::from)
    }
    #[cfg(windows)]
    {
        let _ = (root, parent_relative);
        rename_sibling_no_replace_windows(parent, from, to)
    }
    #[cfg(not(any(target_os = "linux", target_os = "macos", windows)))]
    {
        let _ = (root, parent_relative, parent, from, to);
        Err(std::io::Error::new(
            std::io::ErrorKind::Unsupported,
            "no-replace plugin staging rename is unsupported on this platform",
        ))
    }
}

#[cfg(windows)]
fn rename_sibling_no_replace_windows(
    parent: &cap_std::fs::Dir,
    from: &str,
    to: &str,
) -> std::io::Result<()> {
    use fs_at::os::windows::OpenOptionsExt;
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::Storage::FileSystem::{
        FileRenameInfo, SetFileInformationByHandle, FILE_ADD_FILE, FILE_ADD_SUBDIRECTORY,
        FILE_LIST_DIRECTORY, FILE_READ_ATTRIBUTES, FILE_RENAME_INFO,
    };

    const DELETE_ACCESS: u32 = 0x0001_0000;
    let parent_file = parent.try_clone()?.into_std_file();
    let mut source_options = fs_at::OpenOptions::default();
    source_options.desired_access(DELETE_ACCESS | FILE_READ_ATTRIBUTES);
    let source = source_options.open_path_at(&parent_file, Path::new(from))?;
    let source_metadata = source.metadata()?;
    if super::is_link_or_reparse(&source_metadata) {
        return Err(std::io::Error::other(
            "refusing to rename a plugin link or reparse point",
        ));
    }

    let mut destination_options = fs_at::OpenOptions::default();
    destination_options.desired_access(
        FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES,
    );
    let destination_parent = destination_options.open_dir_at(&parent_file, Path::new("."))?;
    let filename = to.encode_utf16().collect::<Vec<_>>();
    let filename_bytes = filename
        .len()
        .checked_mul(std::mem::size_of::<u16>())
        .and_then(|length| u32::try_from(length).ok())
        .ok_or_else(|| {
            std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "plugin staging name is too long",
            )
        })?;
    let filename_offset = std::mem::offset_of!(FILE_RENAME_INFO, FileName);
    let buffer_bytes = filename_offset + filename.len() * std::mem::size_of::<u16>();
    let word_count = buffer_bytes.div_ceil(std::mem::size_of::<u64>());
    let mut buffer = vec![0_u64; word_count];
    let info = buffer.as_mut_ptr().cast::<FILE_RENAME_INFO>();
    unsafe {
        (*info).RootDirectory = destination_parent.as_raw_handle().cast();
        (*info).FileNameLength = filename_bytes;
        std::ptr::copy_nonoverlapping(
            filename.as_ptr(),
            (*info).FileName.as_mut_ptr(),
            filename.len(),
        );
        if SetFileInformationByHandle(
            source.as_raw_handle().cast(),
            FileRenameInfo,
            info.cast(),
            u32::try_from(buffer_bytes).map_err(|_| {
                std::io::Error::new(
                    std::io::ErrorKind::InvalidInput,
                    "plugin rename information is too large",
                )
            })?,
        ) == 0
        {
            return Err(std::io::Error::last_os_error());
        }
    }
    Ok(())
}

fn stage_exact_file(
    root_path: &Path,
    root: &cap_std::fs::Dir,
    relative: &str,
    digest: &str,
    identity: Option<(u64, u64)>,
    label: &str,
) -> Result<Option<StagedPluginFile>, String> {
    stage_exact_file_with_hardlink_policy(root_path, root, relative, digest, identity, label, false)
}

fn stage_exact_file_with_hardlink_policy(
    root_path: &Path,
    root: &cap_std::fs::Dir,
    relative: &str,
    digest: &str,
    identity: Option<(u64, u64)>,
    label: &str,
    allow_hardlinks: bool,
) -> Result<Option<StagedPluginFile>, String> {
    let Some((parent, name)) = open_relative_parent(root, relative, false)? else {
        return Ok(None);
    };
    let path = plugin_path(root_path, relative);
    let Some(before) =
        read_verified_file_at_with_hardlinks(&parent, &name, &path, allow_hardlinks)?
    else {
        return Ok(None);
    };
    let before_digest = format!("{:x}", sha2::Sha256::digest(&before.bytes));
    if before_digest != digest || identity.is_some_and(|expected| before.identity != expected) {
        return Ok(None);
    }
    #[cfg(unix)]
    ensure_unix_staged_parent_is_not_foreign_writable(&parent, label)?;
    let staged_name = unique_staged_name(&parent)?;
    rename_sibling_no_replace(
        root_path,
        sibling_directory(relative),
        &parent,
        &name,
        &staged_name,
    )
    .map_err(|error| format!("could not stage {label}: {error}"))?;
    let staged_path = path.with_file_name(&staged_name);
    let staged = match read_verified_file_at_with_hardlinks(
        &parent,
        &staged_name,
        &staged_path,
        allow_hardlinks,
    ) {
        Ok(Some(staged)) => staged,
        Ok(None) => return Err(format!("staged {label} disappeared")),
        Err(error) => {
            if let Some(identity) = identity_at(&parent, &staged_name)? {
                if let Err(restore_error) =
                    restore_staged_at(&parent, &staged_name, &name, &staged_path, &path, identity)
                {
                    return Err(format!(
                        "{error}; staged object remains at {}: {restore_error}",
                        staged_path.display()
                    ));
                }
            } else {
                return Err(format!(
                    "{error}; unverified staged object remains at {}",
                    staged_path.display()
                ));
            }
            return Err(error);
        }
    };
    if staged.identity != before.identity
        || format!("{:x}", sha2::Sha256::digest(&staged.bytes)) != digest
    {
        restore_staged_at(
            &parent,
            &staged_name,
            &name,
            &staged_path,
            &path,
            staged.identity,
        )?;
        return Ok(None);
    }
    Ok(Some(StagedPluginFile {
        parent,
        name: staged_name,
        destination_name: name,
        path: staged_path,
        identity: staged.identity,
        digest: digest.to_owned(),
        allow_hardlinks,
    }))
}

fn remove_staged_file_exact(staged: &StagedPluginFile, label: &str) -> Result<(), String> {
    let current = read_verified_file_at_with_hardlinks(
        &staged.parent,
        &staged.name,
        &staged.path,
        staged.allow_hardlinks,
    )?
    .ok_or_else(|| format!("staged {label} disappeared before removal"))?;
    if current.identity != staged.identity
        || format!("{:x}", sha2::Sha256::digest(&current.bytes)) != staged.digest
    {
        return Err(format!(
            "staged {label} changed before removal; it was preserved at {}",
            staged.path.display()
        ));
    }
    remove_verified_file_at(
        &staged.parent,
        &staged.name,
        &staged.path,
        staged.identity,
        &staged.digest,
        staged.allow_hardlinks,
        label,
    )
}

fn restore_staged_file(staged: &StagedPluginFile) -> Result<(), String> {
    let current = read_verified_file_at_with_hardlinks(
        &staged.parent,
        &staged.name,
        &staged.path,
        staged.allow_hardlinks,
    )?
    .ok_or_else(|| "staged plugin file disappeared before restoration".to_owned())?;
    if current.identity != staged.identity
        || format!("{:x}", sha2::Sha256::digest(&current.bytes)) != staged.digest
    {
        return Err(format!(
            "staged plugin file changed before restoration; preserved at {}",
            staged.path.display()
        ));
    }
    staged
        .parent
        .hard_link(&staged.name, &staged.parent, &staged.destination_name)
        .map_err(|error| {
            if error.kind() == std::io::ErrorKind::AlreadyExists {
                format!(
                    "destination changed concurrently; preserved the displaced file at {}",
                    staged.path.display()
                )
            } else {
                format!("could not restore displaced plugin file: {error}")
            }
        })?;
    if identity_at(&staged.parent, &staged.destination_name)? != Some(staged.identity) {
        return Err("restored plugin file identity changed unexpectedly".to_owned());
    }
    remove_verified_file_at(
        &staged.parent,
        &staged.name,
        &staged.path,
        staged.identity,
        &staged.digest,
        true,
        "restored plugin staging file",
    )
}

fn restore_staged_at(
    parent: &cap_std::fs::Dir,
    staged_name: &str,
    destination_name: &str,
    staged_path: &Path,
    destination_path: &Path,
    identity: (u64, u64),
) -> Result<(), String> {
    let current = read_verified_file_at(parent, staged_name, staged_path)?
        .ok_or_else(|| "staged file disappeared before restoration".to_owned())?;
    if current.identity != identity {
        return Err(format!(
            "staged file changed before restoration; preserved at {}",
            staged_path.display()
        ));
    }
    let digest = format!("{:x}", sha2::Sha256::digest(&current.bytes));
    parent
        .hard_link(staged_name, parent, destination_name)
        .map_err(|error| {
            if error.kind() == std::io::ErrorKind::AlreadyExists {
                format!(
                    "destination changed concurrently; preserved the displaced file at {}",
                    staged_path.display()
                )
            } else {
                format!(
                    "could not restore displaced file to {}: {error}",
                    destination_path.display()
                )
            }
        })?;
    if identity_at(parent, destination_name)? != Some(identity) {
        return Err("restored plugin file identity changed unexpectedly".to_owned());
    }
    remove_verified_file_at(
        parent,
        staged_name,
        staged_path,
        identity,
        &digest,
        true,
        "restored plugin staging file",
    )
}

fn restore_backup(
    root: &Path,
    root_dir: &cap_std::fs::Dir,
    backup: &str,
    destination: &str,
    entry: &serde_json::Value,
) -> Result<(), String> {
    let backup_identity = entry
        .get("backup_identity")
        .and_then(serde_json::Value::as_array)
        .and_then(|values| {
            Some((
                python_integer_to_u64(values.first()?)?,
                python_integer_to_u64(values.get(1)?)?,
            ))
        })
        .ok_or_else(|| "plugin ownership state lacks backup identity metadata".to_owned())?;
    let backup_mode = entry
        .get("backup_mode")
        .and_then(python_integer_to_u64)
        .ok_or_else(|| "plugin ownership state lacks backup mode metadata".to_owned())?;
    let backup_mode = u32::try_from(backup_mode)
        .map_err(|_| "plugin ownership state has an invalid backup mode".to_owned())?;
    let Some((backup_parent, backup_name)) = open_relative_parent(root_dir, backup, false)? else {
        return Err("plugin backup parent is unavailable".to_owned());
    };
    let backup_path = plugin_path(root, backup);
    let Some(backup_file) = read_verified_file_at(&backup_parent, &backup_name, &backup_path)?
    else {
        return Err("plugin backup disappeared before restoration".to_owned());
    };
    if !file_matches_backup(&backup_file, entry) {
        return Err("plugin backup changed before restoration; it was preserved".to_owned());
    }
    let Some((destination_parent, destination_name)) =
        open_relative_parent(root_dir, destination, false)?
    else {
        return Err("plugin destination parent is unavailable".to_owned());
    };
    let destination_path = plugin_path(root, destination);
    if let Err(error) =
        backup_parent.hard_link(&backup_name, &destination_parent, &destination_name)
    {
        return Err(if error.kind() == std::io::ErrorKind::AlreadyExists {
            format!(
                "destination appeared during restore; plugin backup preserved: {}",
                destination_path.display()
            )
        } else {
            format!(
                "could not restore plugin backup to {}: {error}",
                destination_path.display()
            )
        });
    }
    if identity_and_mode_at(&destination_parent, &destination_name)?
        != Some((backup_identity, backup_mode))
    {
        return Err(format!(
            "restored plugin backup changed; destination and original backup preserved: {}",
            destination_path.display()
        ));
    }
    let destination_file = read_verified_file_at_with_hardlinks(
        &destination_parent,
        &destination_name,
        &destination_path,
        true,
    )?
    .ok_or_else(|| "restored plugin backup disappeared".to_owned())?;
    if !file_matches_backup(&destination_file, entry) {
        return Err("restored backup changed during finalization".to_owned());
    }
    discard_restored_backup(root, root_dir, backup, entry)?;
    Ok(())
}

fn discard_restored_backup(
    root: &Path,
    root_dir: &cap_std::fs::Dir,
    backup: &str,
    entry: &serde_json::Value,
) -> Result<(), String> {
    let digest = entry
        .get("backup_sha256")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| "plugin ownership state lacks a backup digest".to_owned())?;
    let identity = entry
        .get("backup_identity")
        .and_then(serde_json::Value::as_array)
        .and_then(|values| {
            Some((
                python_integer_to_u64(values.first()?)?,
                python_integer_to_u64(values.get(1)?)?,
            ))
        })
        .ok_or_else(|| "plugin ownership state lacks backup identity metadata".to_owned())?;
    let Some((parent, name)) = open_relative_parent(root_dir, backup, false)? else {
        return Err("plugin backup parent disappeared before cleanup".to_owned());
    };
    let path = plugin_path(root, backup);
    let Some(file) = read_verified_file_at_with_hardlinks(&parent, &name, &path, true)? else {
        return Err("plugin backup disappeared before cleanup".to_owned());
    };
    if !file_matches_backup(&file, entry) {
        return Err("plugin backup changed before cleanup; it was preserved".to_owned());
    }
    remove_verified_file_at(
        &parent,
        &name,
        &path,
        identity,
        digest,
        true,
        "restored plugin backup",
    )
}

fn remove_verified_file_at(
    parent: &cap_std::fs::Dir,
    name: &str,
    path: &Path,
    identity: (u64, u64),
    digest: &str,
    allow_hardlinks: bool,
    label: &str,
) -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        use std::os::windows::io::{AsRawHandle, FromRawHandle};
        use windows_sys::Win32::Foundation::INVALID_HANDLE_VALUE;
        use windows_sys::Win32::Storage::FileSystem::{
            CreateFileW, FileDispositionInfo, SetFileInformationByHandle, FILE_DISPOSITION_INFO,
            FILE_FLAG_OPEN_REPARSE_POINT, FILE_READ_ATTRIBUTES, OPEN_EXISTING,
        };

        const DELETE_ACCESS: u32 = 0x0001_0000;
        const GENERIC_READ: u32 = 0x8000_0000;
        const SHARE_ALL: u32 = 0x0000_0001 | 0x0000_0002 | 0x0000_0004;
        let _ = (parent, name, allow_hardlinks);
        let wide = path
            .as_os_str()
            .encode_wide()
            .chain(std::iter::once(0))
            .collect::<Vec<_>>();
        let handle = unsafe {
            CreateFileW(
                wide.as_ptr(),
                DELETE_ACCESS | GENERIC_READ | FILE_READ_ATTRIBUTES,
                SHARE_ALL,
                std::ptr::null(),
                OPEN_EXISTING,
                FILE_FLAG_OPEN_REPARSE_POINT,
                std::ptr::null_mut(),
            )
        };
        if handle == INVALID_HANDLE_VALUE {
            return Err(format!(
                "could not open staged {label} for identity-bound removal: {}",
                std::io::Error::last_os_error()
            ));
        }
        let mut file = unsafe { std::fs::File::from_raw_handle(handle.cast()) };
        let metadata = file
            .metadata()
            .map_err(|error| format!("could not inspect staged {label}: {error}"))?;
        if !metadata.is_file() || super::is_link_or_reparse(&metadata) {
            return Err(format!(
                "staged {label} changed before removal; it was preserved"
            ));
        }
        let opened_identity = file_identity(&file, &metadata)?;
        let mut bytes = Vec::new();
        file.read_to_end(&mut bytes)
            .map_err(|error| format!("could not verify staged {label}: {error}"))?;
        if opened_identity != identity || format!("{:x}", sha2::Sha256::digest(&bytes)) != digest {
            return Err(format!(
                "staged {label} changed before removal; it was preserved"
            ));
        }
        let disposition = FILE_DISPOSITION_INFO { DeleteFile: 1 };
        let removed = unsafe {
            SetFileInformationByHandle(
                file.as_raw_handle().cast(),
                FileDispositionInfo,
                (&disposition as *const FILE_DISPOSITION_INFO).cast(),
                std::mem::size_of::<FILE_DISPOSITION_INFO>() as u32,
            )
        };
        if removed == 0 {
            return Err(format!(
                "could not remove verified staged {label}: {}",
                std::io::Error::last_os_error()
            ));
        }
        return Ok(());
    }
    #[cfg(unix)]
    {
        let _ = allow_hardlinks;
        ensure_unix_staged_parent_is_not_foreign_writable(parent, label)?;
        let Some(current) =
            read_verified_file_at_with_hardlinks(parent, name, path, allow_hardlinks)?
        else {
            return Err(format!("staged {label} disappeared before removal"));
        };
        if current.identity != identity
            || format!("{:x}", sha2::Sha256::digest(&current.bytes)) != digest
        {
            return Err(format!(
                "staged {label} changed before removal; it was preserved"
            ));
        }
        parent
            .remove_file(name)
            .map_err(|error| format!("could not remove staged {label}: {error}"))
    }
    #[cfg(not(any(windows, unix)))]
    {
        let _ = (parent, name, path, identity, digest, allow_hardlinks, label);
        Err("identity-bound plugin file removal is unsupported on this platform".to_owned())
    }
}

#[cfg(unix)]
fn ensure_unix_staged_parent_is_not_foreign_writable(
    parent: &cap_std::fs::Dir,
    label: &str,
) -> Result<(), String> {
    use std::os::unix::fs::MetadataExt;

    let directory = parent
        .try_clone()
        .map_err(|error| format!("could not inspect {label} parent permissions: {error}"))?
        .into_std_file();
    let metadata = directory
        .metadata()
        .map_err(|error| format!("could not inspect {label} parent permissions: {error}"))?;
    let mode = metadata.mode();
    let owner = metadata.uid();
    let effective_owner = rustix::process::geteuid().as_raw();
    if mode & 0o022 != 0 && mode & 0o1000 == 0 && owner == effective_owner {
        use std::os::unix::fs::PermissionsExt;
        directory
            .set_permissions(std::fs::Permissions::from_mode(mode & !0o022))
            .map_err(|error| {
                format!("could not restrict {label} parent permissions before staging: {error}")
            })?;
        return Ok(());
    }
    if mode & 0o022 != 0 && (mode & 0o1000 == 0 || (owner != effective_owner && owner != 0)) {
        return Err(format!(
            "{label} parent is writable by other users without trusted sticky-bit protection; staged entry was preserved"
        ));
    }
    Ok(())
}

fn identity_at(parent: &cap_std::fs::Dir, name: &str) -> Result<Option<PluginIdentity>, String> {
    Ok(identity_and_mode_at(parent, name)?.map(|(identity, _)| identity))
}

fn identity_and_mode_at(
    parent: &cap_std::fs::Dir,
    name: &str,
) -> Result<Option<PluginIdentityAndMode>, String> {
    let metadata = match parent.symlink_metadata(name) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(format!("could not inspect plugin file identity: {error}")),
    };
    if cap_metadata_is_link_or_reparse(&metadata) || !metadata.is_file() {
        return Ok(None);
    }
    let parent_file = parent
        .try_clone()
        .map_err(|error| format!("could not inspect plugin file identity: {error}"))?
        .into_std_file();
    let mut options = fs_at::OpenOptions::default();
    options.read(true).follow(false);
    let file = match options.open_at(&parent_file, Path::new(name)) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(format!("could not inspect plugin file identity: {error}")),
    };
    let opened = file
        .metadata()
        .map_err(|error| format!("could not inspect plugin file identity: {error}"))?;
    Ok(Some((
        file_identity(&file, &opened)?,
        python_file_mode(&opened),
    )))
}

fn remove_owned_empty_directory(
    root: &Path,
    root_dir: &cap_std::fs::Dir,
    relative: &str,
    identity: (u64, u64),
) -> Result<String, String> {
    if !relative_entry_exists(root, relative)? {
        return Ok("absent".to_owned());
    }
    let Some((parent, name)) = open_relative_parent(root_dir, relative, false)? else {
        return Ok("absent".to_owned());
    };
    let Some(directory_file) = open_existing_directory(&parent, &name)? else {
        return Ok("absent".to_owned());
    };
    if file_identity(
        &directory_file,
        &directory_file
            .metadata()
            .map_err(|error| error.to_string())?,
    )? != identity
    {
        return Ok("preserved (directory identity changed)".to_owned());
    }
    let directory = cap_std::fs::Dir::from_std_file(directory_file);
    if directory
        .entries()
        .map_err(|error| format!("could not inspect managed plugin directory: {error}"))?
        .next()
        .is_some()
    {
        return Ok("preserved (not empty)".to_owned());
    }
    drop(directory);
    #[cfg(unix)]
    ensure_unix_staged_parent_is_not_foreign_writable(&parent, "plugin directory")?;
    let staged = unique_staged_name(&parent)?;
    rename_sibling_no_replace(root, sibling_directory(relative), &parent, &name, &staged)
        .map_err(|error| format!("could not stage managed plugin directory: {error}"))?;
    let Some(staged_file) = open_existing_directory(&parent, &staged)? else {
        return Err(format!(
            "staged managed plugin directory disappeared; inspect {}",
            plugin_path(root, relative)
                .with_file_name(&staged)
                .display()
        ));
    };
    let staged_identity = file_identity(
        &staged_file,
        &staged_file.metadata().map_err(|error| error.to_string())?,
    )?;
    let staged_directory = cap_std::fs::Dir::from_std_file(staged_file);
    if staged_identity != identity
        || staged_directory
            .entries()
            .map_err(|error| format!("could not inspect staged plugin directory: {error}"))?
            .next()
            .is_some()
    {
        drop(staged_directory);
        if staged_identity == identity {
            restore_staged_directory(root, root_dir, relative, &staged, identity)?;
        }
        return Ok("preserved (directory changed concurrently)".to_owned());
    }
    drop(staged_directory);

    // Re-open the staged name immediately before removal. If the directory was
    // replaced or populated after the earlier check, keep it and restore only
    // through a no-replace rename so a concurrent directory is never clobbered.
    let Some(final_file) = open_existing_directory(&parent, &staged)? else {
        return Err(format!(
            "staged managed plugin directory changed before removal; preserved at {}",
            plugin_path(root, relative)
                .with_file_name(&staged)
                .display()
        ));
    };
    let final_identity = file_identity(
        &final_file,
        &final_file.metadata().map_err(|error| error.to_string())?,
    )?;
    let final_directory = cap_std::fs::Dir::from_std_file(final_file);
    if final_identity != identity
        || final_directory
            .entries()
            .map_err(|error| format!("could not recheck staged plugin directory: {error}"))?
            .next()
            .is_some()
    {
        drop(final_directory);
        if final_identity == identity {
            restore_staged_directory(root, root_dir, relative, &staged, identity)?;
        }
        return Ok("preserved (directory changed concurrently)".to_owned());
    }
    drop(final_directory);

    if let Err(error) = remove_staged_directory_exact(root, relative, &parent, &staged, identity) {
        match parent.symlink_metadata(&name) {
            Ok(_) => {
                return Err(format!(
                    "could not remove empty managed directory: {error}; staged directory remains at {}",
                    plugin_path(root, relative).with_file_name(&staged).display()
                ));
            }
            Err(check_error) if check_error.kind() == std::io::ErrorKind::NotFound => {}
            Err(check_error) => {
                return Err(format!(
                    "could not remove empty managed directory: {error}; could not safely inspect its original path: {check_error}"
                ));
            }
        }
        restore_staged_directory(root, root_dir, relative, &staged, identity).map_err(
            |restore| {
                format!(
                "could not remove empty managed directory: {error}; could not restore it: {restore}"
            )
            },
        )?;
        return Err(format!("could not remove empty managed directory: {error}"));
    }
    Ok("removed (empty directory)".to_owned())
}

fn restore_staged_directory(
    root: &Path,
    root_dir: &cap_std::fs::Dir,
    relative: &str,
    staged: &str,
    identity: (u64, u64),
) -> Result<(), String> {
    let Some((parent, destination_name)) = open_relative_parent(root_dir, relative, false)? else {
        return Err(
            "plugin directory parent is unavailable; staged directory was preserved".to_owned(),
        );
    };
    let Some(staged_file) = open_existing_directory(&parent, staged)? else {
        return Err(format!(
            "staged plugin directory disappeared: {}",
            plugin_path(root, relative).with_file_name(staged).display()
        ));
    };
    let staged_identity = file_identity(
        &staged_file,
        &staged_file.metadata().map_err(|error| error.to_string())?,
    )?;
    drop(staged_file);
    if staged_identity != identity {
        return Err(format!(
            "staged plugin directory identity changed; preserved at {}",
            plugin_path(root, relative).with_file_name(staged).display()
        ));
    }
    rename_sibling_no_replace(
        root,
        sibling_directory(relative),
        &parent,
        staged,
        &destination_name,
    )
    .map_err(|error| {
        format!(
            "could not restore staged plugin directory without replacing a concurrent path; preserved at {}: {error}",
            plugin_path(root, relative).with_file_name(staged).display()
        )
    })?;
    let Some(restored) = open_existing_directory(&parent, &destination_name)? else {
        return Err(format!(
            "restored plugin directory disappeared: {}",
            plugin_path(root, relative).display()
        ));
    };
    if file_identity(
        &restored,
        &restored.metadata().map_err(|error| error.to_string())?,
    )? != identity
    {
        return Err(format!(
            "restored plugin directory changed concurrently; inspect {}",
            plugin_path(root, relative).display()
        ));
    }
    Ok(())
}

fn remove_staged_directory_exact(
    root: &Path,
    relative: &str,
    parent: &cap_std::fs::Dir,
    staged: &str,
    identity: (u64, u64),
) -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        use std::os::windows::io::{AsRawHandle, FromRawHandle};
        use windows_sys::Win32::Foundation::INVALID_HANDLE_VALUE;
        use windows_sys::Win32::Storage::FileSystem::{
            CreateFileW, FileDispositionInfo, SetFileInformationByHandle, FILE_DISPOSITION_INFO,
            FILE_FLAG_BACKUP_SEMANTICS, FILE_FLAG_OPEN_REPARSE_POINT, FILE_LIST_DIRECTORY,
            FILE_READ_ATTRIBUTES, OPEN_EXISTING,
        };

        let _ = parent;
        const DELETE_ACCESS: u32 = 0x0001_0000;
        const SHARE_ALL: u32 = 0x0000_0001 | 0x0000_0002 | 0x0000_0004;
        let path = plugin_path(root, relative).with_file_name(staged);
        let wide = path
            .as_os_str()
            .encode_wide()
            .chain(std::iter::once(0))
            .collect::<Vec<_>>();
        let handle = unsafe {
            CreateFileW(
                wide.as_ptr(),
                DELETE_ACCESS | FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY,
                SHARE_ALL,
                std::ptr::null(),
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
                std::ptr::null_mut(),
            )
        };
        if handle == INVALID_HANDLE_VALUE {
            return Err(format!(
                "could not open staged plugin directory for identity-bound removal: {}",
                std::io::Error::last_os_error()
            ));
        }
        let file = unsafe { std::fs::File::from_raw_handle(handle.cast()) };
        let metadata = file
            .metadata()
            .map_err(|error| format!("could not inspect staged plugin directory: {error}"))?;
        if !metadata.is_dir() || super::is_link_or_reparse(&metadata) {
            return Err(
                "staged plugin directory changed before removal; it was preserved".to_owned(),
            );
        }
        if file_identity(&file, &metadata)? != identity {
            return Err("staged plugin directory identity changed before removal".to_owned());
        }
        let directory = cap_std::fs::Dir::from_std_file(
            file.try_clone()
                .map_err(|error| format!("could not recheck staged plugin directory: {error}"))?,
        );
        if directory
            .entries()
            .map_err(|error| format!("could not recheck staged plugin directory: {error}"))?
            .next()
            .is_some()
        {
            return Err("staged plugin directory is no longer empty".to_owned());
        }
        let disposition = FILE_DISPOSITION_INFO { DeleteFile: 1 };
        let removed = unsafe {
            SetFileInformationByHandle(
                file.as_raw_handle().cast(),
                FileDispositionInfo,
                (&disposition as *const FILE_DISPOSITION_INFO).cast(),
                std::mem::size_of::<FILE_DISPOSITION_INFO>() as u32,
            )
        };
        if removed == 0 {
            return Err(format!(
                "could not remove verified staged plugin directory: {}",
                std::io::Error::last_os_error()
            ));
        }
        return Ok(());
    }
    #[cfg(unix)]
    {
        let _ = (root, relative);
        ensure_unix_staged_parent_is_not_foreign_writable(parent, "plugin directory")?;
        let Some(directory_file) = open_existing_directory(parent, staged)? else {
            return Err("staged plugin directory disappeared before removal".to_owned());
        };
        let staged_identity = file_identity(
            &directory_file,
            &directory_file
                .metadata()
                .map_err(|error| error.to_string())?,
        )?;
        let directory = cap_std::fs::Dir::from_std_file(directory_file);
        if staged_identity != identity
            || directory
                .entries()
                .map_err(|error| format!("could not recheck staged plugin directory: {error}"))?
                .next()
                .is_some()
        {
            return Err(
                "staged plugin directory changed before removal; it was preserved".to_owned(),
            );
        }
        parent
            .remove_dir(staged)
            .map_err(|error| format!("could not remove the verified staged directory: {error}"))
    }
    #[cfg(not(any(windows, unix)))]
    {
        let _ = (root, relative, parent, staged, identity);
        Err("identity-bound plugin directory removal is unsupported on this platform".to_owned())
    }
}

fn persist_uninstall_state(
    root: &Path,
    root_dir: &cap_std::fs::Dir,
    plugin: &PluginSpec,
    state: &mut serde_json::Value,
    expected_sha: Option<&str>,
) -> Result<Option<LoadedState>, String> {
    let files_empty = state
        .get("files")
        .and_then(serde_json::Value::as_object)
        .is_none_or(serde_json::Map::is_empty);
    let directories_empty = state
        .get("directories")
        .and_then(serde_json::Value::as_object)
        .is_none_or(serde_json::Map::is_empty);
    if !files_empty || !directories_empty {
        return save_state(root, root_dir, plugin, state, expected_sha).map(Some);
    }

    let current = read_state(root, plugin)?;
    if current.as_ref().map(|loaded| loaded.sha256.as_str()) != expected_sha {
        return Err(
            "plugin ownership state changed concurrently; refusing to remove it".to_owned(),
        );
    }
    if let Some(current) = current {
        let state_dir_file = existing_relative_directory(root_dir, ".agentrouter-state")?
            .ok_or_else(|| "plugin ownership state directory disappeared".to_owned())?;
        let state_dir = cap_std::fs::Dir::from_std_file(state_dir_file);
        let filename = format!("{}.json", plugin.name);
        let path = root.join(".agentrouter-state").join(&filename);
        let Some(file) = read_verified_file_at(&state_dir, &filename, &path)? else {
            return Err("plugin ownership state disappeared before removal".to_owned());
        };
        let digest = format!("{:x}", sha2::Sha256::digest(&file.bytes));
        if digest != current.sha256 {
            return Err(
                "plugin ownership state changed concurrently; refusing to remove it".to_owned(),
            );
        }
        #[cfg(unix)]
        ensure_unix_staged_parent_is_not_foreign_writable(&state_dir, "plugin ownership state")?;
        let staged = unique_staged_name(&state_dir)?;
        rename_sibling_no_replace(root, ".agentrouter-state", &state_dir, &filename, &staged)
            .map_err(|error| {
                format!("could not stage plugin ownership state for removal: {error}")
            })?;
        let staged_path = path.with_file_name(&staged);
        let staged_file = match read_verified_file_at(&state_dir, &staged, &staged_path) {
            Ok(Some(file)) => file,
            Ok(None) => return Err("staged plugin ownership state disappeared".to_owned()),
            Err(error) => {
                if let Some(identity) = identity_at(&state_dir, &staged)? {
                    if let Err(restore_error) = restore_staged_at(
                        &state_dir,
                        &staged,
                        &filename,
                        &staged_path,
                        &path,
                        identity,
                    ) {
                        return Err(format!(
                            "{error}; staged ownership state remains at {}: {restore_error}",
                            staged_path.display()
                        ));
                    }
                } else {
                    return Err(format!(
                        "{error}; unverified ownership state remains at {}",
                        staged_path.display()
                    ));
                }
                return Err(error);
            }
        };
        if staged_file.identity != file.identity || staged_file.bytes != file.bytes {
            restore_staged_at(
                &state_dir,
                &staged,
                &filename,
                &path.with_file_name(&staged),
                &path,
                staged_file.identity,
            )?;
            return Err("plugin ownership state changed while being removed".to_owned());
        }
        let before_remove = read_verified_file_at(&state_dir, &staged, &staged_path)?
            .ok_or_else(|| "staged plugin ownership state disappeared before removal".to_owned())?;
        if before_remove.identity != file.identity || before_remove.bytes != file.bytes {
            return Err(format!(
                "staged plugin ownership state changed before removal; preserved at {}",
                staged_path.display()
            ));
        }
        if let Err(error) = remove_verified_file_at(
            &state_dir,
            &staged,
            &staged_path,
            file.identity,
            &digest,
            false,
            "plugin ownership state",
        ) {
            let restore = restore_staged_at(
                &state_dir,
                &staged,
                &filename,
                &staged_path,
                &path,
                file.identity,
            );
            return match restore {
                Ok(()) => Err(format!("could not remove plugin ownership state: {error}")),
                Err(restore_error) => Err(format!(
                    "could not remove plugin ownership state: {error}; {restore_error}"
                )),
            };
        }
    }

    if let Some(identity) = state
        .get("state_dir_identity")
        .filter(|value| !value.is_null())
    {
        let values = identity.as_array().and_then(|values| {
            Some((
                python_integer_to_u64(values.first()?)?,
                python_integer_to_u64(values.get(1)?)?,
            ))
        });
        if let Some(values) = values {
            let _ = remove_owned_empty_directory(root, root_dir, ".agentrouter-state", values)?;
        }
    }
    Ok(None)
}

fn empty_state(plugin: &PluginSpec) -> serde_json::Value {
    serde_json::json!({
        "schema": 2,
        "plugin": plugin.name,
        "state_dir_identity": null,
        "files": {},
        "directories": {},
    })
}

fn plugin_result(destination: &Path, result: &str) -> serde_json::Value {
    serde_json::json!({
        "kind": "file",
        "dest": destination,
        "result": result,
    })
}

fn existing_relative_directory(
    root: &cap_std::fs::Dir,
    relative: &str,
) -> Result<Option<File>, String> {
    let parts = safe_relative(relative, "plugin directory")?;
    let mut current = root
        .try_clone()
        .map_err(|error| format!("could not inspect plugin root: {error}"))?;
    for part in parts {
        let Some(directory) = open_existing_directory(&current, &part)? else {
            return Ok(None);
        };
        current = cap_std::fs::Dir::from_std_file(directory);
    }
    let directory = current
        .try_clone()
        .map(cap_std::fs::Dir::into_std_file)
        .map_err(|error| format!("could not inspect plugin directory: {error}"))?;
    if relative == ".agentrouter-state" {
        secure_state_directory(&directory)?;
    }
    Ok(Some(directory))
}

fn secure_state_directory(directory: &File) -> Result<(), String> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;

        let metadata = directory
            .metadata()
            .map_err(|error| format!("could not inspect plugin state directory: {error}"))?;
        let owner = metadata.uid();
        let effective_owner = rustix::process::geteuid().as_raw();
        if owner != effective_owner {
            return Err("plugin state directory is not owned by the current user".to_owned());
        }
        if metadata.mode() & 0o077 != 0 {
            use std::os::unix::fs::PermissionsExt;
            directory
                .set_permissions(std::fs::Permissions::from_mode(0o700))
                .map_err(|error| {
                    format!("could not restrict plugin state directory permissions: {error}")
                })?;
        }
    }
    #[cfg(not(unix))]
    let _ = directory;
    Ok(())
}

fn ensure_relative_directory(
    root: &cap_std::fs::Dir,
    relative: &str,
) -> Result<(File, bool), String> {
    let parts = safe_relative(relative, "plugin directory")?;
    let mut current = root
        .try_clone()
        .map_err(|error| format!("could not inspect plugin root: {error}"))?;
    let mut target_created = false;
    for (index, part) in parts.iter().enumerate() {
        let is_target = index + 1 == parts.len();
        if let Some(directory) = open_existing_directory(&current, part)? {
            if relative == ".agentrouter-state" {
                secure_state_directory(&directory)?;
            }
            current = cap_std::fs::Dir::from_std_file(directory);
            continue;
        }
        #[cfg(unix)]
        ensure_unix_staged_parent_is_not_foreign_writable(&current, "plugin directory")?;
        let created = if relative == ".agentrouter-state" {
            #[cfg(unix)]
            {
                use cap_std::fs::DirBuilderExt;
                let mut builder = cap_std::fs::DirBuilder::new();
                builder.mode(0o700);
                current.create_dir_with(part, &builder)
            }
            #[cfg(not(unix))]
            {
                current.create_dir(&part)
            }
        } else {
            #[cfg(unix)]
            {
                use cap_std::fs::DirBuilderExt;
                let mut builder = cap_std::fs::DirBuilder::new();
                builder.mode(0o755);
                current.create_dir_with(part, &builder)
            }
            #[cfg(not(unix))]
            {
                current.create_dir(&part)
            }
        };
        let created_here = match created {
            Ok(()) => true,
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => false,
            Err(error) => return Err(format!("could not create plugin directory: {error}")),
        };
        if is_target {
            target_created = created_here;
        }
        let directory = open_existing_directory(&current, part)?
            .ok_or_else(|| "plugin directory disappeared while being created".to_owned())?;
        if relative == ".agentrouter-state" {
            secure_state_directory(&directory)?;
        }
        current = cap_std::fs::Dir::from_std_file(directory);
    }
    let directory = current
        .try_clone()
        .map(cap_std::fs::Dir::into_std_file)
        .map_err(|error| format!("could not inspect plugin directory: {error}"))?;
    Ok((directory, target_created))
}

fn open_relative_parent(
    root: &cap_std::fs::Dir,
    relative: &str,
    create: bool,
) -> Result<Option<(cap_std::fs::Dir, String)>, String> {
    let parts = safe_relative(relative, "plugin destination")?;
    let Some((filename, directories)) = parts.split_last() else {
        return Ok(None);
    };
    let mut parent = root
        .try_clone()
        .map_err(|error| format!("could not inspect plugin root: {error}"))?;
    for part in directories {
        let directory = match open_existing_directory(&parent, part)? {
            Some(directory) => directory,
            None if create => {
                #[cfg(unix)]
                ensure_unix_staged_parent_is_not_foreign_writable(&parent, "plugin directory")?;
                let created = {
                    #[cfg(unix)]
                    {
                        use cap_std::fs::DirBuilderExt;
                        let mut builder = cap_std::fs::DirBuilder::new();
                        builder.mode(0o755);
                        parent.create_dir_with(part, &builder)
                    }
                    #[cfg(not(unix))]
                    {
                        parent.create_dir(part)
                    }
                };
                match created {
                    Ok(()) => {}
                    Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {}
                    Err(error) => {
                        return Err(format!("could not create plugin directory: {error}"));
                    }
                }
                open_existing_directory(&parent, part)?
                    .ok_or_else(|| "plugin destination directory disappeared".to_owned())?
            }
            None => return Ok(None),
        };
        parent = cap_std::fs::Dir::from_std_file(directory);
    }
    Ok(Some((parent, filename.clone())))
}

fn directory_identity(directory: &File) -> Result<serde_json::Value, String> {
    let metadata = directory
        .metadata()
        .map_err(|error| format!("could not inspect plugin directory identity: {error}"))?;
    let identity = file_identity(directory, &metadata)?;
    Ok(serde_json::json!([identity.0, identity.1]))
}

fn plugin_permissions(mode: u32) -> Option<cap_std::fs::Permissions> {
    #[cfg(unix)]
    {
        use cap_std::fs::PermissionsExt;
        Some(cap_std::fs::Permissions::from_mode(mode))
    }
    #[cfg(not(unix))]
    {
        let _ = mode;
        None
    }
}

fn create_no_clobber(
    parent: &cap_std::fs::Dir,
    name: &str,
    path: &Path,
    contents: &[u8],
    mode: u32,
) -> Result<VerifiedFile, String> {
    #[cfg(unix)]
    ensure_unix_staged_parent_is_not_foreign_writable(parent, "plugin file")?;
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    for _ in 0..16 {
        let candidate = format!(
            ".agentrouter-plugin-{}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_err(|error| error.to_string())?
                .as_nanos(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        );
        let mut options = cap_std::fs::OpenOptions::new();
        options.write(true).create_new(true);
        match parent.open_with(&candidate, &options) {
            Ok(mut temporary) => {
                let result = (|| {
                    if let Some(permissions) = plugin_permissions(mode) {
                        temporary.set_permissions(permissions).map_err(|error| {
                            format!("could not set plugin file permissions: {error}")
                        })?;
                    }
                    temporary
                        .write_all(contents)
                        .map_err(|error| format!("could not write staged plugin file: {error}"))?;
                    temporary
                        .sync_all()
                        .map_err(|error| format!("could not sync staged plugin file: {error}"))?;
                    drop(temporary);
                    let staged_path = path.with_file_name(&candidate);
                    let staged = read_verified_file_at(parent, &candidate, &staged_path)?
                        .ok_or_else(|| "staged plugin file disappeared".to_owned())?;
                    if staged.bytes != contents {
                        return Err("staged plugin file changed before installation".to_owned());
                    }
                    parent
                        .hard_link(&candidate, parent, Path::new(name))
                        .map_err(|error| {
                            if error.kind() == std::io::ErrorKind::AlreadyExists {
                                format!("destination appeared during install; refusing to overwrite it: {}", path.display())
                            } else {
                                format!("could not create destination atomically {}: {error}", path.display())
                            }
                        })?;
                    parent
                        .remove_file(&candidate)
                        .map_err(|error| format!("could not remove staged plugin file: {error}"))?;
                    let installed = read_verified_file_at(parent, name, path)?
                        .ok_or_else(|| "installed plugin file disappeared".to_owned())?;
                    if installed.bytes != contents || installed.identity != staged.identity {
                        return Err("plugin destination changed while being installed".to_owned());
                    }
                    Ok(installed)
                })();
                if result.is_err() {
                    let _ = parent.remove_file(&candidate);
                }
                return result;
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(format!("could not create staged plugin file: {error}")),
        }
    }
    Err("could not create a unique staged plugin file".to_owned())
}

fn save_state(
    root: &Path,
    root_dir: &cap_std::fs::Dir,
    plugin: &PluginSpec,
    state: &mut serde_json::Value,
    expected_sha: Option<&str>,
) -> Result<LoadedState, String> {
    let (directory, _) = ensure_relative_directory(root_dir, ".agentrouter-state")?;
    let identity = directory_identity(&directory)?;
    if state
        .get("state_dir_identity")
        .is_some_and(serde_json::Value::is_null)
    {
        state["state_dir_identity"] = identity;
    } else if state.get("state_dir_identity") != Some(&identity) {
        return Err(
            "plugin private state directory identity changed; refusing to write".to_owned(),
        );
    }
    let current = read_state(root, plugin)?;
    if current.as_ref().map(|loaded| loaded.sha256.as_str()) != expected_sha {
        return Err(
            "plugin ownership state changed concurrently; refusing to overwrite it".to_owned(),
        );
    }
    let serialized = super::contract::dumps(state).map_err(|error| error.to_string())?;
    let state_dir = cap_std::fs::Dir::from_std_file(directory);
    let filename = format!("{}.json", plugin.name);
    if expected_sha.is_none() {
        create_no_clobber(
            &state_dir,
            &filename,
            &root.join(".agentrouter-state").join(&filename),
            serialized.as_bytes(),
            0o600,
        )?;
    } else {
        let mut contents = std::io::Cursor::new(serialized.into_bytes());
        let permissions = plugin_permissions(0o600);
        super::atomic_replace(
            &state_dir,
            Path::new(&filename),
            &mut contents,
            permissions.as_ref(),
        )?;
    }
    read_state(root, plugin)?.ok_or_else(|| "saved plugin ownership state disappeared".to_owned())
}

fn remove_exact_file(
    root: &Path,
    root_dir: &cap_std::fs::Dir,
    relative: &str,
    digest: &str,
    identity: (u64, u64),
) -> Result<bool, String> {
    let Some((parent, name)) = open_relative_parent(root_dir, relative, false)? else {
        return Ok(false);
    };
    let destination = plugin_path(root, relative);
    let Some(current) = read_verified_file_at(&parent, &name, &destination)? else {
        return Ok(false);
    };
    let current_digest = format!("{:x}", sha2::Sha256::digest(&current.bytes));
    if current_digest != digest || current.identity != identity {
        return Ok(false);
    }
    remove_verified_file_at(
        &parent,
        &name,
        &destination,
        identity,
        digest,
        false,
        "new plugin file",
    )?;
    Ok(true)
}

fn diagnose_failure(plugin: &PluginSpec) -> serde_json::Value {
    serde_json::json!({
        "plugin": plugin.name,
        "check": "diagnose",
        "status": "blocked",
        "summary": "the check itself failed (PluginError)",
        "remedy": "this is a bug in the diagnostic; report it",
    })
}

fn diagnosis_for_action(action: &str, plugin_name: &str) -> (&'static str, String, Option<String>) {
    match action {
        "create" => (
            "attention",
            "not installed".to_owned(),
            Some(format!("run: agentrouter plugin install {plugin_name}")),
        ),
        "skip (identical, managed)" => (
            "ok",
            "installed and unmodified".to_owned(),
            None,
        ),
        "adopt identical legacy installation (managed)" => (
            "attention",
            "an identical copy is already here but is not recorded as ours".to_owned(),
            Some(format!(
                "it is byte-for-byte the shipped file, so adopting it changes nothing on disk: agentrouter plugin install {plugin_name} --adopt-identical"
            )),
        ),
        "overwrite (backup first)" => (
            "attention",
            "a different file is at this path — either your edit of ours, or your own".to_owned(),
            Some(format!(
                "it is left alone. To install the shipped version over it: agentrouter plugin install {plugin_name} --force  (the existing file is backed up)"
            )),
        ),
        _ => (
            "blocked",
            "the destination is not a plain file (link, reparse point, or extra hard link)"
                .to_owned(),
            Some("inspect it yourself and move it aside; AgentRouter will not write through it".to_owned()),
        ),
    }
}

fn bundled_contents(source: &str) -> Option<&'static [u8]> {
    match source {
        CLAUDE_SOURCE => Some(include_bytes!(
            "../../../agentrouter/integrations/claude-code/agentrouter/SKILL.md"
        )),
        CODEX_SOURCE => Some(include_bytes!(
            "../../../agentrouter/integrations/codex/AGENTS.md"
        )),
        _ => None,
    }
}

fn path_entry_exists(path: &Path) -> Result<bool, String> {
    match std::fs::symlink_metadata(path) {
        Ok(_) => Ok(true),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(error) => Err(format!(
            "could not check whether {} exists: {error}",
            path.display()
        )),
    }
}

fn check_link_components(root: &Path, relative: &str) -> Result<(), String> {
    let parts = safe_relative(relative, "plugin destination")?;
    let mut current = root.to_path_buf();
    check_component(&current)?;
    for part in parts {
        current.push(part);
        check_component(&current)?;
    }
    Ok(())
}

fn check_component(path: &Path) -> Result<(), String> {
    match std::fs::symlink_metadata(path) {
        Ok(metadata) if super::is_link_or_reparse(&metadata) => Err(format!(
            "unsafe destination contains a link or reparse point: {}",
            path.display()
        )),
        Ok(_) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(format!("could not inspect {}: {error}", path.display())),
    }
}

fn relative_entry_exists(root: &Path, relative: &str) -> Result<bool, String> {
    let parts = safe_relative(relative, "plugin destination")?;
    let Some((filename, directories)) = parts.split_last() else {
        return Ok(false);
    };
    let root_file = match std::fs::symlink_metadata(root) {
        Ok(metadata) if !super::is_link_or_reparse(&metadata) && metadata.is_dir() => {
            super::open_safe_home(root)?
        }
        Ok(_) => return Err("plugin root is not a safe directory".to_owned()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(format!("could not inspect plugin root: {error}")),
    };
    let mut parent = cap_std::fs::Dir::from_std_file(root_file);
    for part in directories {
        let Some(directory) = open_existing_directory(&parent, part)? else {
            return Ok(false);
        };
        parent = cap_std::fs::Dir::from_std_file(directory);
    }
    match parent.symlink_metadata(filename) {
        Ok(_) => Ok(true),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(error) => Err(format!("could not inspect plugin path: {error}")),
    }
}

fn read_relative_file(root: &Path, relative: &str) -> Result<Option<VerifiedFile>, String> {
    let parts = safe_relative(relative, "plugin destination")?;
    let Some((filename, directories)) = parts.split_last() else {
        return Ok(None);
    };
    let root_file = match std::fs::symlink_metadata(root) {
        Ok(metadata) if !super::is_link_or_reparse(&metadata) && metadata.is_dir() => {
            super::open_safe_home(root)?
        }
        Ok(_) => return Err("plugin root is not a safe directory".to_owned()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(format!("could not inspect plugin root: {error}")),
    };
    let mut parent = cap_std::fs::Dir::from_std_file(root_file);
    for part in directories {
        let Some(directory) = open_existing_directory(&parent, part)? else {
            return Ok(None);
        };
        parent = cap_std::fs::Dir::from_std_file(directory);
    }
    let path = plugin_path(root, relative);
    read_verified_file_at(&parent, filename, &path)
}

fn safe_path_exists(root: &cap_std::fs::Dir, relative: &str) -> Result<bool, String> {
    let parts = safe_relative(relative, "plugin destination")?;
    let Some((filename, directories)) = parts.split_last() else {
        return Ok(false);
    };
    let mut parent = root
        .try_clone()
        .map_err(|error| format!("could not inspect plugin root: {error}"))?;
    for part in directories {
        let file = open_existing_directory(&parent, part)?;
        let Some(file) = file else {
            return Ok(false);
        };
        parent = cap_std::fs::Dir::from_std_file(file);
    }
    let metadata = match parent.symlink_metadata(filename) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(format!("could not inspect plugin destination: {error}")),
    };
    if cap_metadata_is_link_or_reparse(&metadata) {
        return Err("plugin destination contains a link or reparse point".to_owned());
    }
    Ok(true)
}

fn open_existing_directory(
    parent: &cap_std::fs::Dir,
    name: &str,
) -> Result<Option<std::fs::File>, String> {
    let parent_file = parent
        .try_clone()
        .map_err(|error| format!("could not inspect plugin destination: {error}"))?
        .into_std_file();
    let mut options = fs_at::OpenOptions::default();
    options.read(true).follow(false);
    let opened = match options.open_dir_at(&parent_file, Path::new(name)) {
        Ok(opened) => opened,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(format!("could not inspect plugin directory: {error}")),
    };
    let metadata = opened
        .metadata()
        .map_err(|error| format!("could not inspect plugin directory: {error}"))?;
    if super::is_link_or_reparse(&metadata) {
        return Err("plugin destination contains a link or reparse point".to_owned());
    }
    Ok(Some(opened))
}

fn cap_metadata_is_link_or_reparse(metadata: &cap_std::fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use cap_std::fs::MetadataExt;
        metadata.file_type().is_symlink() || metadata.file_attributes() & 0x400 != 0
    }
    #[cfg(not(windows))]
    {
        metadata.file_type().is_symlink()
    }
}

/// Ownership state successfully read and validated without following links.
#[derive(Debug, Clone, PartialEq)]
pub struct LoadedState {
    pub value: serde_json::Value,
    pub sha256: String,
}

/// Read the per-plugin ownership record through pinned directory handles.
/// Missing root/state directories or state files mean no installed ownership
/// record. Links, reparse points, hard links, unstable reads, malformed JSON,
/// and invalid claims fail closed.
pub fn read_state(root: &Path, plugin: &PluginSpec) -> Result<Option<LoadedState>, String> {
    match std::fs::symlink_metadata(root) {
        Ok(metadata) if !super::is_link_or_reparse(&metadata) && metadata.is_dir() => {}
        Ok(_) => {
            return Err(format!(
                "plugin destination root is not a safe directory: {}",
                root.display()
            ))
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => {
            return Err(format!(
                "could not inspect plugin root {}: {error}",
                root.display()
            ))
        }
    }
    let root_file = super::open_safe_home(root)?;
    let root_dir = cap_std::fs::Dir::from_std_file(root_file);
    let Some(state_dir) = existing_relative_directory(&root_dir, ".agentrouter-state")? else {
        return Ok(None);
    };
    let state_dir = cap_std::fs::Dir::from_std_file(state_dir);
    let filename = format!("{}.json", plugin.name);
    let path = root.join(".agentrouter-state").join(&filename);
    let Some(verified) = read_verified_file_at(&state_dir, &filename, &path)? else {
        return Ok(None);
    };
    let value: serde_json::Value = serde_json::from_slice(&verified.bytes).map_err(|_| {
        format!(
            "plugin ownership state is invalid; refusing to continue: {}",
            path.display()
        )
    })?;
    validate_state_data(plugin, &value)?;
    let sha256 = format!("{:x}", sha2::Sha256::digest(&verified.bytes));
    Ok(Some(LoadedState { value, sha256 }))
}

fn read_verified_file_at(
    parent: &cap_std::fs::Dir,
    name: &str,
    path: &Path,
) -> Result<Option<VerifiedFile>, String> {
    read_verified_file_at_with_hardlinks(parent, name, path, false)
}

fn read_verified_file_at_with_hardlinks(
    parent: &cap_std::fs::Dir,
    name: &str,
    path: &Path,
    allow_hardlinks: bool,
) -> Result<Option<VerifiedFile>, String> {
    let before = match parent.symlink_metadata(name) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => {
            return Err(format!(
                "could not check whether plugin ownership state exists at {}: {error}",
                path.display()
            ));
        }
    };
    if cap_metadata_is_link_or_reparse(&before) || !before.is_file() {
        return Err(format!(
            "plugin ownership state is not a regular non-link file; refusing to modify it: {}",
            path.display()
        ));
    }
    if !allow_hardlinks && super::has_multiple_links(parent, name, &before)? {
        return Err(format!(
            "plugin ownership state has multiple hard links; refusing to modify it: {}",
            path.display()
        ));
    }

    let parent_file = parent
        .try_clone()
        .map_err(|error| {
            format!(
                "could not safely open plugin ownership state {}: {error}",
                path.display()
            )
        })?
        .into_std_file();
    let mut options = fs_at::OpenOptions::default();
    options.read(true).follow(false);
    let mut file = options
        .open_at(&parent_file, Path::new(name))
        .map_err(|error| {
            format!(
                "could not safely open plugin ownership state {}: {error}",
                path.display()
            )
        })?;
    let opened = file.metadata().map_err(|error| {
        format!(
            "could not inspect plugin ownership state {}: {error}",
            path.display()
        )
    })?;
    if !opened.is_file() || super::is_link_or_reparse(&opened) {
        return Err(format!(
            "plugin ownership state changed while it was being opened: {}",
            path.display()
        ));
    }
    let opened_fingerprint = file_fingerprint(&file, &opened)?;
    let mut raw = Vec::new();
    file.read_to_end(&mut raw).map_err(|error| {
        format!(
            "could not safely read plugin ownership state {}: {error}",
            path.display()
        )
    })?;
    let after_handle = file.metadata().map_err(|error| {
        format!(
            "could not inspect plugin ownership state {}: {error}",
            path.display()
        )
    })?;
    let after_path = match parent.symlink_metadata(name) {
        Ok(metadata) => metadata,
        Err(error) => {
            return Err(format!(
                "plugin ownership state changed while it was being read: {} ({error})",
                path.display()
            ));
        }
    };
    if cap_metadata_is_link_or_reparse(&after_path)
        || !after_path.is_file()
        || (!allow_hardlinks && super::has_multiple_links(parent, name, &after_path)?)
        || file_fingerprint(&file, &after_handle)? != opened_fingerprint
        || after_path.len() != opened_fingerprint.len
        || after_path
            .modified()
            .ok()
            .map(cap_std::time::SystemTime::into_std)
            != Some(opened_fingerprint.modified)
    {
        return Err(format!(
            "plugin ownership state changed while it was being read: {}",
            path.display()
        ));
    }

    // Re-open the final component without following it to detect a pathname
    // replacement that occurred while the pinned handle was being read.
    let parent_file = parent
        .try_clone()
        .map_err(|error| {
            format!(
                "could not verify plugin ownership state {}: {error}",
                path.display()
            )
        })?
        .into_std_file();
    let final_file = options
        .open_at(&parent_file, Path::new(name))
        .map_err(|error| {
            format!(
                "plugin ownership state changed while it was being read: {} ({error})",
                path.display()
            )
        })?;
    let final_metadata = final_file.metadata().map_err(|error| {
        format!(
            "could not verify plugin ownership state {}: {error}",
            path.display()
        )
    })?;
    if file_fingerprint(&final_file, &final_metadata)? != opened_fingerprint {
        return Err(format!(
            "plugin ownership state changed while it was being read: {}",
            path.display()
        ));
    }
    Ok(Some(VerifiedFile {
        bytes: raw,
        identity: opened_fingerprint.identity,
        mode: python_file_mode(&opened),
    }))
}

#[derive(Debug)]
struct VerifiedFile {
    bytes: Vec<u8>,
    identity: (u64, u64),
    mode: u32,
}

type PluginIdentity = (u64, u64);
type PluginIdentityAndMode = (PluginIdentity, u32);

#[cfg(unix)]
fn python_file_mode(metadata: &std::fs::Metadata) -> u32 {
    use std::os::unix::fs::MetadataExt;
    metadata.mode() & 0o7777
}

#[cfg(windows)]
fn python_file_mode(metadata: &std::fs::Metadata) -> u32 {
    if metadata.permissions().readonly() {
        0o444
    } else {
        0o666
    }
}

#[cfg(not(any(unix, windows)))]
fn python_file_mode(_metadata: &std::fs::Metadata) -> u32 {
    0
}

#[derive(Debug, PartialEq, Eq)]
struct FileFingerprint {
    identity: (u64, u64),
    len: u64,
    modified: SystemTime,
}

fn file_fingerprint(file: &File, metadata: &std::fs::Metadata) -> Result<FileFingerprint, String> {
    let identity = file_identity(file, metadata)?;
    let modified = metadata
        .modified()
        .map_err(|error| format!("could not verify plugin ownership state timestamp: {error}"))?;
    Ok(FileFingerprint {
        identity,
        len: metadata.len(),
        modified,
    })
}

#[cfg(unix)]
fn file_identity(_file: &File, metadata: &std::fs::Metadata) -> Result<(u64, u64), String> {
    use std::os::unix::fs::MetadataExt;
    Ok((metadata.dev(), metadata.ino()))
}

#[cfg(windows)]
fn file_identity(file: &File, _metadata: &std::fs::Metadata) -> Result<(u64, u64), String> {
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::Foundation::HANDLE;
    use windows_sys::Win32::Storage::FileSystem::{
        FileIdInfo, GetFileInformationByHandle, GetFileInformationByHandleEx,
        BY_HANDLE_FILE_INFORMATION, FILE_ID_INFO,
    };
    let handle = file.as_raw_handle() as HANDLE;
    let mut extended = std::mem::MaybeUninit::<FILE_ID_INFO>::uninit();
    // Python 3.12+ uses FILE_ID_INFO for os.stat identity. Keep the ownership
    // record byte-compatible while rejecting 128-bit file IDs that the current
    // two-integer state schema cannot represent losslessly.
    if unsafe {
        GetFileInformationByHandleEx(
            handle,
            FileIdInfo,
            extended.as_mut_ptr().cast(),
            std::mem::size_of::<FILE_ID_INFO>() as u32,
        )
    } != 0
    {
        let information = unsafe { extended.assume_init() };
        let low = u64::from_le_bytes(
            information.FileId.Identifier[..8]
                .try_into()
                .map_err(|_| "could not read plugin file identity".to_owned())?,
        );
        let high = u64::from_le_bytes(
            information.FileId.Identifier[8..]
                .try_into()
                .map_err(|_| "could not read plugin file identity".to_owned())?,
        );
        if high != 0 {
            return Err(
                "plugin file identity exceeds the current ownership-state representation"
                    .to_owned(),
            );
        }
        return Ok((information.VolumeSerialNumber, low));
    }

    let mut information = std::mem::MaybeUninit::<BY_HANDLE_FILE_INFORMATION>::uninit();
    // SAFETY: `file` owns a valid open handle and the Win32 API initializes the
    // structure before it is read on success.
    if unsafe { GetFileInformationByHandle(handle, information.as_mut_ptr()) } == 0 {
        return Err(format!(
            "could not verify plugin ownership state identity: {}",
            std::io::Error::last_os_error()
        ));
    }
    // SAFETY: the successful API call above initialized the structure.
    let information = unsafe { information.assume_init() };
    let file_index =
        (u64::from(information.nFileIndexHigh) << 32) | u64::from(information.nFileIndexLow);
    Ok((u64::from(information.dwVolumeSerialNumber), file_index))
}

#[cfg(not(any(unix, windows)))]
fn file_identity(_file: &File, _metadata: &std::fs::Metadata) -> Result<(u64, u64), String> {
    Err("plugin ownership state identity is unsupported on this platform".to_owned())
}

/// Validate the JSON ownership-record shape without claiming any filesystem
/// path. Callers must still open the record without following links and verify
/// its digest/inode before using these claims to mutate a destination.
pub fn validate_state_data(plugin: &PluginSpec, state: &serde_json::Value) -> Result<(), String> {
    let path_for = |category: &str| format!("plugin ownership state {category}");
    let Some(object) = state.as_object() else {
        return Err("plugin ownership state has an unsupported schema".to_owned());
    };
    if !object
        .get("schema")
        .is_some_and(python_equal_schema_version)
        || object.get("plugin").and_then(serde_json::Value::as_str) != Some(plugin.name)
        || !object
            .get("files")
            .is_some_and(serde_json::Value::is_object)
        || !object
            .get("directories")
            .is_some_and(serde_json::Value::is_object)
    {
        return Err(path_for("has an unsupported schema"));
    }
    let files = object
        .get("files")
        .and_then(serde_json::Value::as_object)
        .expect("files shape checked above");
    for (relative, entry) in files {
        safe_relative(relative, "plugin destination")?;
        let Some(entry) = entry.as_object() else {
            return Err(format!(
                "plugin ownership state contains an invalid destination: {}",
                python_string_repr(relative)
            ));
        };
        if !matches!(
            entry.get("disposition").and_then(serde_json::Value::as_str),
            Some("created" | "replaced" | "preexisting")
        ) {
            return Err(format!(
                "plugin ownership state contains an invalid disposition: {}",
                python_string_repr(relative)
            ));
        }
        if !entry
            .get("installed_sha256")
            .is_some_and(serde_json::Value::is_string)
        {
            return Err(format!(
                "plugin ownership state lacks an installed digest: {}",
                python_string_repr(relative)
            ));
        }
        if !valid_identity(entry.get("installed_identity")) {
            return Err(format!(
                "plugin ownership state lacks a valid file identity: {}",
                python_string_repr(relative)
            ));
        }
        if let Some(backup) = entry.get("backup").filter(|value| !value.is_null()) {
            let Some(backup) = backup.as_str() else {
                return Err(format!(
                    "unsafe relative path for plugin backup in ownership state: {}",
                    python_string_repr(&backup.to_string())
                ));
            };
            safe_relative(backup, "plugin backup in ownership state")?;
            if !entry
                .get("backup_sha256")
                .is_some_and(serde_json::Value::is_string)
            {
                return Err(format!(
                    "plugin ownership state lacks a backup digest: {}",
                    python_string_repr(relative)
                ));
            }
            if !valid_identity(entry.get("backup_identity"))
                || !entry.get("backup_mode").is_some_and(is_python_integer)
            {
                return Err(format!(
                    "plugin ownership state lacks backup identity metadata: {}",
                    python_string_repr(relative)
                ));
            }
        }
    }
    let directories = object
        .get("directories")
        .and_then(serde_json::Value::as_object)
        .expect("directories shape checked above");
    for (relative, entry) in directories {
        safe_relative(relative, "managed plugin directory")?;
        if !entry
            .as_object()
            .and_then(|entry| entry.get("identity"))
            .is_some_and(|identity| valid_identity(Some(identity)))
        {
            return Err(format!(
                "plugin ownership state has invalid directory identity: {}",
                python_string_repr(relative)
            ));
        }
    }
    if let Some(identity) = object.get("state_dir_identity") {
        if !identity.is_null() && !valid_identity(Some(identity)) {
            return Err(
                "plugin ownership state has an invalid private-directory identity".to_owned(),
            );
        }
    }
    Ok(())
}

fn valid_identity(value: Option<&serde_json::Value>) -> bool {
    value
        .and_then(serde_json::Value::as_array)
        .is_some_and(|identity| identity.len() == 2 && identity.iter().all(is_python_integer))
}

fn is_python_integer(value: &serde_json::Value) -> bool {
    value.is_boolean() || value.as_i64().is_some() || value.as_u64().is_some()
}

fn python_equal_schema_version(value: &serde_json::Value) -> bool {
    !value.is_boolean() && value.as_f64() == Some(2.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plugin_inventory_matches_python_order_and_paths() {
        let plugins = known_plugins();
        assert_eq!(
            plugins.iter().map(|plugin| plugin.name).collect::<Vec<_>>(),
            ["claude-code", "codex"]
        );
        assert_eq!(plugins[0].files[0].src, "claude-code/agentrouter/SKILL.md");
        assert_eq!(plugins[0].files[0].dest, "skills/agentrouter/SKILL.md");
        assert_eq!(plugins[0].cleanup_dirs, ["skills/agentrouter"]);
        assert_eq!(plugins[1].files[0].src, "codex/AGENTS.md");
        assert_eq!(plugins[1].files[0].dest, "AGENTS.md");
        assert!(plugins[1].cleanup_dirs.is_empty());
    }

    #[test]
    fn paths_are_normalized_without_losing_safe_whitespace() {
        assert_eq!(
            safe_relative("a\\b c\\file.md", "d").unwrap(),
            ["a", "b c", "file.md"]
        );
        assert_eq!(
            safe_relative("NUL\u{2003}.txt", "d").unwrap(),
            ["NUL\u{2003}.txt"]
        );
        assert_eq!(safe_relative("CONSOLE.md", "d").unwrap(), ["CONSOLE.md"]);
        assert_eq!(safe_relative("COM10", "d").unwrap(), ["COM10"]);
    }

    #[test]
    fn paths_reject_traversal_aliases_and_windows_device_names() {
        for value in [
            "",
            "../escape.md",
            "..\\escape.md",
            "/absolute.md",
            "//server/share",
            "C:\\temp\\file",
            "a//b",
            "a/./b",
            "a/../b",
            "trailing./file",
            "trailing /file",
            "NUL",
            "com1.txt",
            "LPT9.log",
            "a\u{1f}b",
            "a?b",
            "a:b",
        ] {
            assert!(
                safe_relative(value, "plugin destination").is_err(),
                "{value:?}"
            );
        }
    }

    #[test]
    fn roots_obey_override_and_home_precedence() {
        let plugin = get_plugin("claude-code").unwrap();
        assert_eq!(
            dest_root(
                plugin,
                Some(Path::new("/tmp/plugin-root")),
                Some(Path::new("/home/u"))
            )
            .unwrap(),
            PathBuf::from("/tmp/plugin-root/claude-code")
        );
        assert_eq!(
            dest_root(plugin, None, Some(Path::new("/home/u"))).unwrap(),
            PathBuf::from("/home/u/.claude")
        );
    }

    #[test]
    fn ownership_state_shape_matches_python_integer_and_optional_fields() {
        let plugin = get_plugin("codex").unwrap();
        let valid = serde_json::json!({
            "schema": 2,
            "plugin": "codex",
            "state_dir_identity": [true, 42],
            "files": {
                "AGENTS.md": {
                    "disposition": "replaced",
                    "installed_sha256": "abc",
                    "installed_identity": [1, 2],
                    "backup": "AGENTS.md.agentrouter-bak",
                    "backup_sha256": "def",
                    "backup_identity": [3, 4],
                    "backup_mode": 384
                }
            },
            "directories": {"skills": {"identity": [5, 6]}}
        });
        assert!(validate_state_data(plugin, &valid).is_ok());
        let mut float_schema_version = valid.clone();
        float_schema_version["schema"] = serde_json::json!(2.0);
        assert!(validate_state_data(plugin, &float_schema_version).is_ok());
        assert!(validate_state_data(
            plugin,
            &serde_json::json!({"schema":2,"plugin":"codex","files":{},"directories":{}})
        )
        .is_ok());
    }

    #[test]
    fn ownership_state_shape_rejects_untrusted_claims() {
        let plugin = get_plugin("codex").unwrap();
        let invalid = [
            serde_json::json!([]),
            serde_json::json!({"schema":1,"plugin":"codex","files":{},"directories":{}}),
            serde_json::json!({"schema":2,"plugin":"claude-code","files":{},"directories":{}}),
            serde_json::json!({"schema":2,"plugin":"codex","files":[],"directories":{}}),
            serde_json::json!({"schema":2,"plugin":"codex","files":{"../escape":{}},"directories":{}}),
            serde_json::json!({"schema":2,"plugin":"codex","files":{"AGENTS.md":{}},"directories":{}}),
            serde_json::json!({"schema":2,"plugin":"codex","files":{"AGENTS.md":{"disposition":"unknown"}},"directories":{}}),
            serde_json::json!({"schema":2,"plugin":"codex","files":{"AGENTS.md":{"disposition":"created","installed_sha256":"abc","installed_identity":[1.5,2]}},"directories":{}}),
            serde_json::json!({"schema":2,"plugin":"codex","files":{"AGENTS.md":{"disposition":"created","installed_sha256":"abc","installed_identity":[1,2],"backup":"../outside"}},"directories":{}}),
            serde_json::json!({"schema":2,"plugin":"codex","files":{},"directories":{"skills":{"identity":[1]}}}),
            serde_json::json!({"schema":2,"plugin":"codex","files":{},"directories":{},"state_dir_identity":[1,2,3]}),
        ];
        for state in invalid {
            assert!(validate_state_data(plugin, &state).is_err(), "{state}");
        }
    }

    #[test]
    fn backup_restore_rejects_payload_not_matching_ownership_record() {
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join("home");
        std::fs::create_dir_all(&root).unwrap();
        let backup = "AGENTS.md.agentrouter-bak";
        std::fs::write(root.join(backup), b"keep this backup").unwrap();
        let root_file = crate::open_safe_home(&root).unwrap();
        let root_dir = cap_std::fs::Dir::from_std_file(root_file);
        let file = read_relative_file(&root, backup).unwrap().unwrap();
        let entry = serde_json::json!({
            "backup_sha256": "0".repeat(64),
            "backup_identity": [file.identity.0, file.identity.1],
            "backup_mode": file.mode,
        });

        let error = restore_backup(&root, &root_dir, backup, "AGENTS.md", &entry).unwrap_err();

        assert!(error.contains("plugin backup changed"));
        assert_eq!(
            std::fs::read(root.join(backup)).unwrap(),
            b"keep this backup"
        );
        assert!(!root.join("AGENTS.md").exists());
        assert_eq!(std::fs::read_dir(&root).unwrap().count(), 1);
    }

    #[test]
    fn uninstall_recovers_backup_linked_before_cleanup_was_interrupted() {
        #[cfg(unix)]
        use std::os::unix::fs::PermissionsExt;

        let plugin = get_plugin("codex").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join("home");
        std::fs::create_dir_all(&root).unwrap();
        #[cfg(unix)]
        std::fs::set_permissions(&root, std::fs::Permissions::from_mode(0o700)).unwrap();
        let destination = "AGENTS.md";
        let backup = "AGENTS.md.agentrouter-bak";
        std::fs::write(root.join(destination), b"managed plugin bytes").unwrap();
        std::fs::write(root.join(backup), b"original user bytes").unwrap();
        let managed = read_relative_file(&root, destination).unwrap().unwrap();
        let original = read_relative_file(&root, backup).unwrap().unwrap();
        let root_file = crate::open_safe_home(&root).unwrap();
        let root_dir = cap_std::fs::Dir::from_std_file(root_file);
        let mut state = empty_state(plugin);
        state["files"][destination] = serde_json::json!({
            "disposition": "replaced",
            "installed_sha256": format!("{:x}", sha2::Sha256::digest(&managed.bytes)),
            "installed_identity": [managed.identity.0, managed.identity.1],
            "backup": backup,
            "backup_sha256": format!("{:x}", sha2::Sha256::digest(&original.bytes)),
            "backup_identity": [original.identity.0, original.identity.1],
            "backup_mode": original.mode,
        });
        save_state(&root, &root_dir, plugin, &mut state, None).unwrap();

        // Model a process stop after linking the backup to its destination but
        // before unlinking the canonical backup path.
        std::fs::remove_file(root.join(destination)).unwrap();
        std::fs::hard_link(root.join(backup), root.join(destination)).unwrap();

        let results = uninstall(plugin, &root).unwrap();

        assert!(results
            .iter()
            .any(|result| { result["result"] == "recovered completed backup restoration" }));
        assert_eq!(
            std::fs::read(root.join(destination)).unwrap(),
            b"original user bytes"
        );
        assert!(!root.join(backup).exists());
        assert!(!root.join(".agentrouter-state").exists());
    }

    #[test]
    fn staged_file_removal_preserves_a_replacement_at_the_staging_name() {
        #[cfg(unix)]
        use std::os::unix::fs::PermissionsExt;

        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join("home");
        std::fs::create_dir_all(&root).unwrap();
        #[cfg(unix)]
        std::fs::set_permissions(&root, std::fs::Permissions::from_mode(0o700)).unwrap();
        let destination = "managed.md";
        std::fs::write(root.join(destination), b"managed payload").unwrap();
        let root_file = crate::open_safe_home(&root).unwrap();
        let root_dir = cap_std::fs::Dir::from_std_file(root_file);
        let installed = read_relative_file(&root, destination).unwrap().unwrap();
        let digest = format!("{:x}", sha2::Sha256::digest(&installed.bytes));
        let staged = stage_exact_file(
            &root,
            &root_dir,
            destination,
            &digest,
            Some(installed.identity),
            "managed plugin file",
        )
        .unwrap()
        .unwrap();
        let moved = root.join("saved-managed-file");
        std::fs::rename(&staged.path, &moved).unwrap();
        std::fs::write(&staged.path, b"unrelated file").unwrap();

        let error = remove_staged_file_exact(&staged, "managed plugin file").unwrap_err();

        assert!(error.contains("changed before removal"));
        assert_eq!(std::fs::read(&moved).unwrap(), b"managed payload");
        assert_eq!(std::fs::read(&staged.path).unwrap(), b"unrelated file");
    }

    #[cfg(unix)]
    #[test]
    fn plugin_uninstall_restricts_writable_staging_parent_before_mutation() {
        use std::os::unix::fs::{MetadataExt, PermissionsExt};

        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join("home");
        let parent = root.join("shared");
        std::fs::create_dir_all(&parent).unwrap();
        let destination = "shared/managed.md";
        std::fs::write(root.join(destination), b"managed payload").unwrap();
        std::fs::set_permissions(&parent, std::fs::Permissions::from_mode(0o777)).unwrap();
        let root_file = crate::open_safe_home(&root).unwrap();
        let root_dir = cap_std::fs::Dir::from_std_file(root_file);
        let managed = read_relative_file(&root, destination).unwrap().unwrap();
        let digest = format!("{:x}", sha2::Sha256::digest(&managed.bytes));

        let (shared_dir, _) = open_relative_parent(&root_dir, "shared/new.md", false)
            .unwrap()
            .unwrap();
        let created = create_no_clobber(
            &shared_dir,
            "new.md",
            &root.join("shared/new.md"),
            b"new payload",
            0o644,
        )
        .unwrap();
        assert_eq!(created.bytes, b"new payload");
        assert_eq!(std::fs::metadata(&parent).unwrap().mode() & 0o777, 0o755);

        let staged = stage_exact_file(
            &root,
            &root_dir,
            destination,
            &digest,
            Some(managed.identity),
            "managed plugin file",
        )
        .unwrap()
        .unwrap();

        restore_staged_file(&staged).unwrap();
        assert_eq!(
            std::fs::read(root.join(destination)).unwrap(),
            b"managed payload"
        );
        assert_eq!(
            std::fs::read(root.join("shared/new.md")).unwrap(),
            b"new payload"
        );
    }

    #[cfg(unix)]
    #[test]
    fn python_style_state_directory_permissions_are_restricted_on_read() {
        use std::os::unix::fs::{MetadataExt, PermissionsExt};

        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join("home");
        std::fs::create_dir_all(root.join(".agentrouter-state")).unwrap();
        std::fs::set_permissions(
            root.join(".agentrouter-state"),
            std::fs::Permissions::from_mode(0o755),
        )
        .unwrap();
        assert!(read_state(&root, get_plugin("codex").unwrap())
            .unwrap()
            .is_none());

        assert_eq!(
            std::fs::metadata(root.join(".agentrouter-state"))
                .unwrap()
                .mode()
                & 0o777,
            0o700
        );
    }

    #[cfg(unix)]
    #[test]
    fn cleanup_directory_created_after_initial_check_is_not_claimed() {
        let plugin = get_plugin("claude-code").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join("home");
        std::fs::create_dir_all(&root).unwrap();
        let root_file = crate::open_safe_home(&root).unwrap();
        let root_dir = cap_std::fs::Dir::from_std_file(root_file);
        let relative = plugin.cleanup_dirs[0];

        assert!(existing_relative_directory(&root_dir, relative)
            .unwrap()
            .is_none());
        std::fs::create_dir_all(plugin_path(&root, relative)).unwrap();

        let (_, created) = ensure_relative_directory(&root_dir, relative).unwrap();

        assert!(!created);
    }

    #[test]
    fn sibling_no_replace_rename_preserves_a_concurrent_directory() {
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap();
        std::fs::create_dir(root.join("staged")).unwrap();
        std::fs::create_dir(root.join("destination")).unwrap();
        std::fs::write(root.join("staged/owned"), b"owned").unwrap();
        std::fs::write(root.join("destination/concurrent"), b"keep").unwrap();
        let root_file = crate::open_safe_home(&root).unwrap();
        let root_dir = cap_std::fs::Dir::from_std_file(root_file);

        let error =
            rename_sibling_no_replace(&root, "", &root_dir, "staged", "destination").unwrap_err();

        assert_eq!(error.kind(), std::io::ErrorKind::AlreadyExists);
        assert_eq!(std::fs::read(root.join("staged/owned")).unwrap(), b"owned");
        assert_eq!(
            std::fs::read(root.join("destination/concurrent")).unwrap(),
            b"keep"
        );
    }

    #[test]
    fn status_reports_missing_and_present_destinations() {
        let plugin = get_plugin("codex").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join(plugin.name);
        assert_eq!(status(plugin, &root), "not-installed");
        std::fs::create_dir_all(&root).unwrap();
        assert_eq!(status(plugin, &root), "not-installed");
        std::fs::write(root.join("AGENTS.md"), "user file").unwrap();
        assert_eq!(status(plugin, &root), "installed");
    }

    #[cfg(unix)]
    #[test]
    fn status_fails_closed_on_linked_destinations() {
        use std::os::unix::fs::symlink;

        let plugin = get_plugin("claude-code").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join(plugin.name);
        let destination = root.join("skills/agentrouter/SKILL.md");
        std::fs::create_dir_all(destination.parent().unwrap()).unwrap();
        let outside = temporary.path().join("outside.md");
        std::fs::write(&outside, "leave unchanged").unwrap();
        symlink(&outside, &destination).unwrap();
        assert_eq!(status(plugin, &root), "blocked");
        assert_eq!(std::fs::read_to_string(outside).unwrap(), "leave unchanged");
    }

    #[test]
    fn reads_valid_ownership_state_and_matches_its_digest() {
        let plugin = get_plugin("codex").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join(plugin.name);
        std::fs::create_dir_all(root.join(".agentrouter-state")).unwrap();
        let raw = br#"{"schema":2,"plugin":"codex","state_dir_identity":null,"files":{},"directories":{}}"#;
        let path = root.join(".agentrouter-state/codex.json");
        std::fs::write(&path, raw).unwrap();

        let loaded = read_state(&root, plugin).unwrap().unwrap();
        assert_eq!(loaded.value["plugin"], "codex");
        assert_eq!(loaded.sha256, format!("{:x}", sha2::Sha256::digest(raw)));
    }

    #[test]
    fn missing_root_state_directory_and_record_are_absent() {
        let plugin = get_plugin("codex").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join(plugin.name);
        assert!(read_state(&root, plugin).unwrap().is_none());
        std::fs::create_dir_all(&root).unwrap();
        assert!(read_state(&root, plugin).unwrap().is_none());
        std::fs::create_dir_all(root.join(".agentrouter-state")).unwrap();
        assert!(read_state(&root, plugin).unwrap().is_none());
    }

    #[test]
    fn malformed_and_invalid_ownership_records_fail_closed() {
        let plugin = get_plugin("codex").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join(plugin.name);
        let state_dir = root.join(".agentrouter-state");
        std::fs::create_dir_all(&state_dir).unwrap();
        let path = state_dir.join("codex.json");
        std::fs::write(&path, b"not JSON").unwrap();
        assert!(read_state(&root, plugin)
            .unwrap_err()
            .contains("ownership state is invalid"));
        std::fs::write(
            &path,
            br#"{"schema":2,"plugin":"codex","files":{"../escape":{}},"directories":{}}"#,
        )
        .unwrap();
        assert!(read_state(&root, plugin)
            .unwrap_err()
            .contains("unsafe relative path"));
    }

    #[cfg(unix)]
    #[test]
    fn ownership_state_reader_rejects_symlinks_and_hardlinks() {
        use std::fs::hard_link;
        use std::os::unix::fs::symlink;

        let plugin = get_plugin("codex").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join(plugin.name);
        let state_dir = root.join(".agentrouter-state");
        std::fs::create_dir_all(&state_dir).unwrap();
        let state = state_dir.join("codex.json");
        let external = temporary.path().join("external.json");
        std::fs::write(
            &external,
            br#"{"schema":2,"plugin":"codex","files":{},"directories":{}}"#,
        )
        .unwrap();
        symlink(&external, &state).unwrap();
        assert!(read_state(&root, plugin).is_err());
        std::fs::remove_file(&state).unwrap();
        std::fs::write(
            &state,
            br#"{"schema":2,"plugin":"codex","files":{},"directories":{}}"#,
        )
        .unwrap();
        let linked = temporary.path().join("linked.json");
        hard_link(&state, linked).unwrap();
        assert!(read_state(&root, plugin)
            .unwrap_err()
            .contains("hard links"));
    }

    #[cfg(unix)]
    #[test]
    fn ownership_state_reader_rejects_a_symlinked_state_directory() {
        use std::os::unix::fs::symlink;

        let plugin = get_plugin("codex").unwrap();
        let temporary = tempfile::tempdir().unwrap();
        let root = temporary.path().canonicalize().unwrap().join(plugin.name);
        let external = temporary.path().join("external-state");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::create_dir_all(&external).unwrap();
        symlink(&external, root.join(".agentrouter-state")).unwrap();
        assert!(read_state(&root, plugin).is_err());
    }
}
