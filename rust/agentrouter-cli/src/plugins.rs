//! Plugin manifest metadata and portable path validation.
//!
//! This is the first Rust slice of `agentrouter.plugins`. It deliberately ports
//! the trust boundary before filesystem mutation: plugin names and manifest
//! paths are checked with the same cross-platform rules as Python.

use std::path::{Path, PathBuf};

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
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        use cap_std::fs::MetadataExt;
        metadata.file_attributes() & 0x400 != 0
    }
    #[cfg(not(windows))]
    {
        false
    }
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
        let root = temporary.path().join(plugin.name);
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
        let root = temporary.path().join(plugin.name);
        let destination = root.join("skills/agentrouter/SKILL.md");
        std::fs::create_dir_all(destination.parent().unwrap()).unwrap();
        let outside = temporary.path().join("outside.md");
        std::fs::write(&outside, "leave unchanged").unwrap();
        symlink(&outside, &destination).unwrap();
        assert_eq!(status(plugin, &root), "blocked");
        assert_eq!(std::fs::read_to_string(outside).unwrap(), "leave unchanged");
    }
}
