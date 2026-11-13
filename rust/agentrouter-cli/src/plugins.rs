//! Plugin manifest metadata and portable path validation.
//!
//! This is the first Rust slice of `agentrouter.plugins`. It deliberately ports
//! the trust boundary before filesystem mutation: plugin names and manifest
//! paths are checked with the same cross-platform rules as Python.

use std::fs::File;
use std::io::Read;
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
            "remedy": format!("re-run it to recover: agentrouter plugin install {}", plugin.name),
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
        let destination = root.join(file.dest);
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
        let destination = root.join(file.dest);
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
    let path = root.join(relative);
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
    let Some(state_dir) = open_existing_directory(&root_dir, ".agentrouter-state")? else {
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
    if super::has_multiple_links(parent, name, &before)? {
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
        || super::has_multiple_links(parent, name, &after_path)?
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
    }))
}

#[derive(Debug)]
struct VerifiedFile {
    bytes: Vec<u8>,
    identity: (u64, u64),
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
    use windows_sys::Win32::Storage::FileSystem::{
        GetFileInformationByHandle, BY_HANDLE_FILE_INFORMATION,
    };
    let mut information = std::mem::MaybeUninit::<BY_HANDLE_FILE_INFORMATION>::uninit();
    // SAFETY: `file` owns a valid open handle and the Win32 API initializes the
    // structure before it is read on success.
    if unsafe { GetFileInformationByHandle(file.as_raw_handle(), information.as_mut_ptr()) } == 0 {
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
