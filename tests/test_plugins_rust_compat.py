"""Differential checks for the Rust plugin manifest and path-safety slice."""

import json
import multiprocessing
import os
import subprocess
import time
from pathlib import Path

import pytest

from agentrouter import plugins


def _rust_plugin_probe(payload: dict) -> dict:
    repository = Path(__file__).resolve().parents[1]
    binary = (
        "plugin_state_from_json"
        if "states" in payload or "reads" in payload
        else "plugin_paths_from_json"
    )
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            binary,
        ],
        cwd=repository,
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


def test_rust_plugin_inventory_matches_python():
    payload = {"plugins": [*plugins.PLUGINS, "missing\nplugin\u202e"]}
    actual = _rust_plugin_probe(payload)["plugins"]
    expected = [
        {
            "name": plugin.name,
            "description": plugin.description,
            "files": [{"src": file.src, "dest": file.dest} for file in plugin.files],
            "home_subdir": plugin._home_subdir,
            "cleanup_dirs": list(plugin.cleanup_dirs),
        }
        for plugin in plugins.PLUGINS.values()
    ]
    try:
        plugins.get_plugin("missing\nplugin\u202e")
    except plugins.PluginError as error:
        expected_error = str(error)
    expected.append({"error": expected_error})
    assert actual[:2] == expected[:2]
    assert actual[2] == expected[2]


def test_rust_portable_path_validation_matches_python():
    values = [
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
        "CON",
        "nul.txt",
        "com1.txt",
        "LPT9.log",
        "a\x01b",
        "a?b",
        "a:b",
        "a\\b c\\file.md",
        "NUL\u2003.txt",
        "CONSOLE.md",
        "COM10",
        "ab .md",
        "name with spaces.md",
    ]
    actual = _rust_plugin_probe(
        {"paths": [{"value": value, "label": "plugin destination"} for value in values]}
    )["paths"]
    for value, result in zip(values, actual, strict=True):
        try:
            expected = plugins._safe_relative(value, "plugin destination")
        except plugins.PluginError:
            assert result["accepted"] is False, value
        else:
            assert result["accepted"] is True, value
            assert result["parts"] == list(expected.parts), value


def test_rust_plugin_destination_roots_match_python(tmp_path, monkeypatch):
    override = tmp_path / "plug-root"
    home = tmp_path / "user home"
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(override))
    expected_override = [str(plugins.dest_root(plugin)) for plugin in plugins.PLUGINS.values()]
    monkeypatch.delenv("AGENTROUTER_PLUGIN_ROOT")
    monkeypatch.setattr(Path, "home", lambda: home)
    expected_home = [str(plugins.dest_root(plugin)) for plugin in plugins.PLUGINS.values()]

    payload = {
        "roots": [
            {"plugin": name, "override": str(override), "home": str(home)}
            for name in plugins.PLUGINS
        ]
        + [{"plugin": name, "override": "", "home": str(home)} for name in plugins.PLUGINS]
    }
    actual = _rust_plugin_probe(payload)["roots"]
    assert [item["path"] for item in actual[:2]] == expected_override
    assert [item["path"] for item in actual[2:]] == expected_home


def test_rust_ownership_state_validation_matches_python(tmp_path):
    plugin = plugins.get_plugin("codex")
    valid = plugins._empty_state(plugin)
    valid["state_dir_identity"] = [True, 42]  # Python treats bool as an int.
    valid["files"] = {
        "AGENTS.md": {
            "disposition": "replaced",
            "installed_sha256": "abc",
            "installed_identity": [1, 2],
            "backup": "AGENTS.md.agentrouter-bak",
            "backup_sha256": "def",
            "backup_identity": [3, 4],
            "backup_mode": 384,
        }
    }
    valid["directories"] = {"skills": {"identity": [5, 6]}}
    float_schema_version = {**valid, "schema": 2.0}
    states = [
        json.dumps(valid),
        json.dumps(float_schema_version),
        "{not json",
        json.dumps({"schema": 1, "plugin": "codex", "files": {}, "directories": {}}),
        json.dumps({"schema": 2, "plugin": "other", "files": {}, "directories": {}}),
        json.dumps({"schema": 2, "plugin": "codex", "files": [], "directories": {}}),
        json.dumps(
            {
                "schema": 2,
                "plugin": "codex",
                "files": {"../escape": {}},
                "directories": {},
            }
        ),
        json.dumps(
            {
                "schema": 2,
                "plugin": "codex",
                "files": {"AGENTS.md": {"disposition": "created"}},
                "directories": {},
            }
        ),
        json.dumps(
            {
                "schema": 2,
                "plugin": "codex",
                "files": {
                    "AGENTS.md": {
                        "disposition": "created",
                        "installed_sha256": "abc",
                        "installed_identity": [1.5, 2],
                    }
                },
                "directories": {},
            }
        ),
        json.dumps(
            {
                "schema": 2,
                "plugin": "codex",
                "files": {
                    "AGENTS.md": {
                        "disposition": "created",
                        "installed_sha256": "abc",
                        "installed_identity": [1, 2],
                        "backup": "../outside",
                    }
                },
                "directories": {},
            }
        ),
        json.dumps(
            {
                "schema": 2,
                "plugin": "codex",
                "files": {},
                "directories": {"skills": {"identity": [1]}},
            }
        ),
        json.dumps(
            {
                "schema": 2,
                "plugin": "codex",
                "files": {},
                "directories": {},
                "state_dir_identity": [1, 2, 3],
            }
        ),
    ]

    expected = []
    for index, raw in enumerate(states):
        root = tmp_path / str(index)
        state_path = plugins._state_path(root, plugin)
        state_path.parent.mkdir(parents=True)
        state_path.write_text(raw, encoding="utf-8")
        try:
            plugins._load_state(root, plugin)
        except plugins.PluginError:
            expected.append(False)
        else:
            expected.append(True)

    actual = _rust_plugin_probe(
        {"states": [{"plugin": plugin.name, "state_raw": raw} for raw in states]}
    )["states"]
    assert [item["accepted"] for item in actual] == expected


def test_rust_ownership_state_disk_reader_matches_python(tmp_path):
    plugin = plugins.get_plugin("codex")
    root = tmp_path / plugin.name

    def rust_read():
        return _rust_plugin_probe({"reads": [{"plugin": plugin.name, "root": str(root)}]})["reads"][
            0
        ]

    expected_empty, empty_digest = plugins._load_state(root, plugin)
    missing = rust_read()
    assert missing == {"accepted": True, "state": None, "sha256": None}
    assert empty_digest is None

    state_path = plugins._state_path(root, plugin)
    state_path.parent.mkdir(parents=True)
    raw = plugins._serialized_state(plugins._empty_state(plugin))
    state_path.write_bytes(raw)
    expected_state, expected_digest = plugins._load_state(root, plugin)
    loaded = rust_read()
    assert loaded["accepted"] is True
    assert loaded["state"] == expected_state == expected_empty
    assert loaded["sha256"] == expected_digest

    state_path.write_bytes(b"not JSON")
    with pytest.raises(plugins.PluginError):
        plugins._load_state(root, plugin)
    assert rust_read()["accepted"] is False

    state_path.unlink()
    outside = tmp_path / "outside.json"
    outside.write_bytes(raw)
    try:
        state_path.symlink_to(outside)
    except OSError:
        pass
    else:
        with pytest.raises(plugins.PluginError):
            plugins._load_state(root, plugin)
        assert rust_read()["accepted"] is False
        state_path.unlink()

    state_path.write_bytes(raw)
    linked_copy = tmp_path / "linked-state.json"
    try:
        linked_copy.hardlink_to(state_path)
    except OSError:
        pytest.skip("hard links are unavailable")
    with pytest.raises(plugins.PluginError):
        plugins._load_state(root, plugin)
    assert rust_read()["accepted"] is False


def _rust_plugin_command(*args: str) -> subprocess.CompletedProcess[str]:
    repository = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "agentrouter",
            "--",
            *args,
        ],
        cwd=repository,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def _rust_plugin_list() -> subprocess.CompletedProcess[str]:
    return _rust_plugin_command("plugin", "list")


def _rust_plugin_doctor() -> subprocess.CompletedProcess[str]:
    return _rust_plugin_command("plugin", "doctor", "--json")


def _rust_plugin_install_dry_run(
    plugin_name: str, *options: str
) -> subprocess.CompletedProcess[str]:
    return _rust_plugin_command("plugin", "install", plugin_name, *options, "--dry-run")


def _rust_plugin_install(plugin_name: str, *options: str) -> subprocess.CompletedProcess[str]:
    return _rust_plugin_command("plugin", "install", plugin_name, *options)


def _rust_plugin_uninstall(plugin_name: str) -> subprocess.CompletedProcess[str]:
    return _rust_plugin_command("plugin", "uninstall", plugin_name)


def _hold_python_plugin_lock(root: str, plugin_name: str, ready, release) -> None:
    plugin = plugins.get_plugin(plugin_name)
    with plugins._process_lock_for(Path(root), plugin):
        ready.set()
        release.wait(20)


def _prepare_python_interrupted_replacement(plugin, root, *, phase, replace=False):
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("original user content", encoding="utf-8")
    original = plugins._regular_lstat(destination, "test destination")
    expected = plugins._src_bytes(plugin.files[0].src)
    transaction = {
        "schema": 1,
        "plugin": plugin.name,
        "phase": "prepared",
        "dest": plugin.files[0].dest,
        "backup": plugins._backup_path(root, destination).relative_to(root).as_posix(),
        "original_sha256": plugins._sha256(destination.read_bytes()),
        "original_identity": plugins._identity_json(original),
        "original_mode": original.st_mode & 0o7777,
        "installed_sha256": plugins._sha256(expected),
    }
    plugins._write_transaction(root, plugin, transaction)
    backup_digest, backup_info = plugins._create_backup(
        root, destination, plugins._backup_path(root, destination)
    )
    transaction["phase"] = phase
    plugins._write_transaction(root, plugin, transaction)
    if replace:
        installed = plugins._atomic_replace_bytes(root, destination, expected, mode=0o644)
        transaction["phase"] = "replaced"
        transaction["installed_identity"] = plugins._identity_json(installed)
        plugins._write_transaction(root, plugin, transaction)
    return destination, expected, transaction, backup_digest, backup_info


def _expected_plugin_list() -> str:
    return "".join(
        f"{plugin.name:<12} [{plugins.status(plugin)}]  {plugin.description}\n"
        for plugin in plugins.PLUGINS.values()
    )


def test_rust_plugin_list_matches_python_for_absent_and_present_files(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    absent = _rust_plugin_list()
    assert absent.returncode == 0, absent.stderr
    assert absent.stdout == _expected_plugin_list()

    plugin = plugins.get_plugin("codex")
    destination = plugins.dest_root(plugin) / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_text("existing user file", encoding="utf-8")
    present = _rust_plugin_list()
    assert present.returncode == 0, present.stderr
    assert present.stdout == _expected_plugin_list()


def test_rust_plugin_list_reports_linked_destinations_as_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("claude-code")
    destination = plugins.dest_root(plugin) / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("leave unchanged", encoding="utf-8")
    try:
        destination.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    process = _rust_plugin_list()
    assert process.returncode == 0, process.stderr
    assert process.stdout == _expected_plugin_list()
    assert "[blocked]" in process.stdout
    assert outside.read_text(encoding="utf-8") == "leave unchanged"


def test_rust_plugin_doctor_matches_python_through_install_and_corrupt_state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))

    def assert_doctor_matches_python(expected_code):
        findings = plugins.diagnose_all()
        expected = {"status": plugins.worst_status(findings), "findings": findings}
        process = _rust_plugin_doctor()
        assert process.returncode == expected_code, process.stderr
        assert json.loads(process.stdout) == expected

    assert_doctor_matches_python(2)
    plugin = plugins.get_plugin("codex")
    destination = plugins.dest_root(plugin) / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_bytes(plugins._src_bytes(plugin.files[0].src))
    assert_doctor_matches_python(2)

    destination.write_text("user-authored plugin guidance", encoding="utf-8")
    assert_doctor_matches_python(2)

    destination.unlink()
    plugins.install(plugin)
    plugins.install(plugins.get_plugin("claude-code"))
    assert_doctor_matches_python(0)

    plugins._state_path(plugins.dest_root(plugin), plugin).write_bytes(b"corrupt state")
    assert_doctor_matches_python(1)


def test_rust_plugin_doctor_matches_python_for_unsafe_destinations(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("claude-code")
    destination = plugins.dest_root(plugin) / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("leave unchanged", encoding="utf-8")
    try:
        destination.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    findings = plugins.diagnose_all()
    expected = {"status": plugins.worst_status(findings), "findings": findings}
    process = _rust_plugin_doctor()
    assert process.returncode == 1, process.stderr
    assert json.loads(process.stdout) == expected
    assert outside.read_text(encoding="utf-8") == "leave unchanged"


def test_rust_plugin_doctor_documents_transaction_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    transaction = {
        "schema": 1,
        "plugin": plugin.name,
        "phase": "prepared",
        "dest": plugin.files[0].dest,
        "backup": f"{plugin.files[0].dest}{plugins._BAK_SUFFIX}",
        "original_sha256": "0" * 64,
        "original_identity": [1, 2],
        "original_mode": 0o644,
        "installed_sha256": "1" * 64,
    }
    plugins._write_transaction(root, plugin, transaction)

    findings = plugins.diagnose_all()
    expected = {"status": plugins.worst_status(findings), "findings": findings}
    process = _rust_plugin_doctor()
    assert process.returncode == 2, process.stderr
    assert json.loads(process.stdout) == expected
    transaction_path = plugins._transaction_path(root, plugin)
    refused = _rust_plugin_uninstall(plugin.name)
    assert refused.returncode != 0
    assert "unexpected destination" in refused.stderr
    assert transaction_path.is_file()


def test_rust_install_recovers_python_crash_after_replacement_before_state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination, expected, transaction, backup_digest, backup_info = (
        _prepare_python_interrupted_replacement(plugin, root, phase="backed_up", replace=True)
    )
    assert "replaced" == transaction["phase"]
    assert not plugins._state_path(root, plugin).exists()

    recovered = _rust_plugin_install(plugin.name)
    assert recovered.returncode == 0, recovered.stderr
    assert "skipped (identical, managed)" in recovered.stdout
    assert destination.read_bytes() == expected
    assert not plugins._transaction_path(root, plugin).exists()
    state = plugins._load_state(root, plugin)[0]
    entry = state["files"][plugin.files[0].dest]
    assert entry["disposition"] == "replaced"
    assert entry["backup_sha256"] == backup_digest
    assert entry["backup_identity"] == plugins._identity_json(backup_info)

    removed = plugins.uninstall(plugin)
    assert any(item["result"] == "removed (restored backup)" for item in removed)
    assert destination.read_text(encoding="utf-8") == "original user content"


def test_rust_install_recovers_python_crash_after_backup_before_replace(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination, _, _, _, _ = _prepare_python_interrupted_replacement(
        plugin, root, phase="backed_up"
    )
    backup = plugins._backup_path(root, destination)

    refused = _rust_plugin_install(plugin.name)

    assert refused.returncode != 0
    assert "exists and differs" in refused.stderr
    assert destination.read_text(encoding="utf-8") == "original user content"
    assert not backup.exists()
    assert not plugins._transaction_path(root, plugin).exists()


def test_rust_recovery_clears_backed_up_journal_when_backup_was_not_created(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination, _, _, _, _ = _prepare_python_interrupted_replacement(
        plugin, root, phase="backed_up"
    )
    backup = plugins._backup_path(root, destination)
    backup.unlink()

    refused = _rust_plugin_install(plugin.name)

    assert refused.returncode != 0
    assert "exists and differs" in refused.stderr
    assert destination.read_text(encoding="utf-8") == "original user content"
    assert not backup.exists()
    assert not plugins._transaction_path(root, plugin).exists()


def test_rust_recovery_does_not_misread_a_preexisting_state_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_text("original user content", encoding="utf-8")
    original, original_info = plugins._read_verified(destination, "test destination")
    state = plugins._empty_state(plugin)
    state["files"][plugin.files[0].dest] = {
        "disposition": "preexisting",
        "installed_sha256": plugins._sha256(original),
        "installed_identity": plugins._identity_json(original_info),
        "backup": None,
    }
    plugins._save_state(root, plugin, state)
    _, _, _, _, _ = _prepare_python_interrupted_replacement(plugin, root, phase="backed_up")

    forced = _rust_plugin_install(plugin.name, "--force")

    assert forced.returncode == 0, forced.stderr
    assert destination.read_bytes() == plugins._src_bytes(plugin.files[0].src)
    assert (
        destination.with_name(destination.name + plugins._BAK_SUFFIX).read_text(encoding="utf-8")
        == "original user content"
    )
    state = plugins._load_state(root, plugin)[0]
    assert state["files"][plugin.files[0].dest]["disposition"] == "replaced"
    assert not plugins._transaction_path(root, plugin).exists()


def test_rust_replaced_recovery_requires_the_recorded_installed_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination, expected, _, _, _ = _prepare_python_interrupted_replacement(
        plugin, root, phase="replaced", replace=True
    )
    original_installed_identity = plugins._identity_json(destination.stat())
    replacement = destination.with_name("replacement.tmp")
    replacement.write_bytes(expected)
    replacement.replace(destination)
    assert plugins._identity_json(destination.stat()) != original_installed_identity

    refused = _rust_plugin_install(plugin.name)

    assert refused.returncode != 0
    assert "ambiguous" in refused.stderr
    assert destination.read_bytes() == expected
    assert plugins._backup_path(root, destination).read_text(encoding="utf-8") == (
        "original user content"
    )
    assert plugins._transaction_path(root, plugin).is_file()


def test_rust_recovery_restores_original_staged_before_install(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination, _, transaction, _, _ = _prepare_python_interrupted_replacement(
        plugin, root, phase="backed_up"
    )
    staging = destination.with_name(".agentrouter-remove-python-interruption")
    transaction["staged"] = staging.relative_to(root).as_posix()
    plugins._write_transaction(root, plugin, transaction)
    destination.replace(staging)

    refused = _rust_plugin_install(plugin.name)

    assert refused.returncode != 0
    assert "exists and differs" in refused.stderr
    assert destination.read_text(encoding="utf-8") == "original user content"
    assert not staging.exists()
    assert not plugins._backup_path(root, destination).exists()
    assert not plugins._transaction_path(root, plugin).exists()


def test_rust_install_preserves_ambiguous_transaction_and_user_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination, _, _, _, _ = _prepare_python_interrupted_replacement(
        plugin, root, phase="backed_up"
    )
    backup = plugins._backup_path(root, destination)
    plugins._atomic_replace_bytes(root, destination, b"concurrent user edit")

    refused = _rust_plugin_install(plugin.name, "--force")

    assert refused.returncode != 0
    assert "ambiguous" in refused.stderr
    assert destination.read_bytes() == b"concurrent user edit"
    assert backup.read_text(encoding="utf-8") == "original user content"
    assert plugins._transaction_path(root, plugin).is_file()


def test_rust_install_fails_closed_on_corrupt_transaction_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    transaction_path = plugins._transaction_path(root, plugin)
    transaction_path.parent.mkdir(parents=True)
    transaction_path.write_text("{broken", encoding="utf-8")

    refused = _rust_plugin_install(plugin.name)

    assert refused.returncode != 0
    assert "transaction journal is invalid" in refused.stderr
    assert transaction_path.read_text(encoding="utf-8") == "{broken"


def test_rust_install_does_not_claim_a_prepared_phase_backup_collision(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_text("original user content", encoding="utf-8")
    original = plugins._regular_lstat(destination, "test destination")
    backup = plugins._backup_path(root, destination)
    transaction = {
        "schema": 1,
        "plugin": plugin.name,
        "phase": "prepared",
        "dest": plugin.files[0].dest,
        "backup": backup.relative_to(root).as_posix(),
        "original_sha256": plugins._sha256(destination.read_bytes()),
        "original_identity": plugins._identity_json(original),
        "original_mode": original.st_mode & 0o7777,
        "installed_sha256": plugins._sha256(plugins._src_bytes(plugin.files[0].src)),
    }
    plugins._write_transaction(root, plugin, transaction)
    backup.write_text("another actor's backup", encoding="utf-8")

    refused = _rust_plugin_install(plugin.name)

    assert refused.returncode != 0
    assert "exists and differs" in refused.stderr
    assert destination.read_text(encoding="utf-8") == "original user content"
    assert backup.read_text(encoding="utf-8") == "another actor's backup"
    assert not plugins._transaction_path(root, plugin).exists()


def test_rust_force_install_interoperates_with_python_uninstall_and_backup_mode(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_text("user-authored guidance", encoding="utf-8")
    destination.chmod(0o600)
    original = destination.stat()

    forced = _rust_plugin_install(plugin.name, "--force")
    assert forced.returncode == 0, forced.stderr
    assert destination.read_bytes() == plugins._src_bytes(plugin.files[0].src)
    backup = plugins._backup_path(root, destination)
    assert backup.read_text(encoding="utf-8") == "user-authored guidance"
    assert backup.stat().st_ino == original.st_ino
    assert backup.stat().st_mode & 0o777 == original.st_mode & 0o777
    assert not plugins._transaction_path(root, plugin).exists()

    removed = plugins.uninstall(plugin)
    assert any(item["result"] == "removed (restored backup)" for item in removed)
    assert destination.read_text(encoding="utf-8") == "user-authored guidance"
    assert destination.stat().st_mode & 0o777 == original.st_mode & 0o777
    assert not backup.exists()


def test_rust_mutation_waits_for_python_process_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    repository = Path(__file__).resolve().parents[1]
    binary_name = "agentrouter.exe" if os.name == "nt" else "agentrouter"
    binary = repository / "target" / "debug" / binary_name

    assert _rust_plugin_list().returncode == 0
    assert binary.is_file()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    holder = context.Process(
        target=_hold_python_plugin_lock,
        args=(str(root), plugin.name, ready, release),
    )
    holder.start()
    try:
        assert ready.wait(20), "Python worker did not acquire the plugin lock"
        mutation = subprocess.Popen(
            [str(binary), "plugin", "install", plugin.name],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        time.sleep(0.3)
        assert mutation.poll() is None, "Rust mutation bypassed the Python-held lock"
    finally:
        release.set()
        holder.join(20)
    assert holder.exitcode == 0
    stdout, stderr = mutation.communicate(timeout=120)
    assert mutation.returncode == 0, stderr
    assert "created" in stdout


def test_rust_plugin_install_dry_run_matches_python_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    destination = plugins.dest_root(plugin) / plugin.files[0].dest

    def assert_plan_matches_python(*options, adopt_identical=False):
        items = plugins.plan(plugin, adopt_identical=adopt_identical)
        expected = f"Would install '{plugin.name}':\n" + "".join(
            f"  {item['action']:<24} {item['dest']}\n" for item in items
        )
        process = _rust_plugin_install_dry_run(plugin.name, *options)
        assert process.returncode == 0, process.stderr
        assert process.stdout == expected

    assert_plan_matches_python()

    destination.parent.mkdir(parents=True)
    destination.write_bytes(plugins._src_bytes(plugin.files[0].src))
    assert_plan_matches_python()
    assert_plan_matches_python("--adopt-identical", adopt_identical=True)

    destination.write_text("user-authored plugin guidance", encoding="utf-8")
    assert_plan_matches_python()

    destination.unlink()
    plugins.install(plugin)
    assert_plan_matches_python()


def test_rust_plugin_install_creates_python_compatible_state_and_is_idempotent(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest

    first = _rust_plugin_install(plugin.name)
    assert first.returncode == 0, first.stderr
    assert "created" in first.stdout
    assert destination.read_bytes() == plugins._src_bytes(plugin.files[0].src)
    state, _ = plugins._load_state(root, plugin)
    assert state["files"][plugin.files[0].dest]["disposition"] == "created"
    assert state["files"][plugin.files[0].dest]["backup"] is None
    assert plugins._state_path(root, plugin).read_bytes() == plugins._serialized_state(state)

    second = _rust_plugin_install(plugin.name)
    assert second.returncode == 0, second.stderr
    assert "skipped (identical, managed)" in second.stdout
    assert destination.read_bytes() == plugins._src_bytes(plugin.files[0].src)

    removed = _rust_plugin_uninstall(plugin.name)
    assert removed.returncode == 0, removed.stderr
    assert "removed" in removed.stdout
    assert not destination.exists()
    assert not plugins._state_path(root, plugin).exists()


def test_rust_plugin_install_tracks_claude_cleanup_directory_for_python_uninstall(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("claude-code")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    cleanup_directory = root / plugin.cleanup_dirs[0]

    installed = _rust_plugin_install(plugin.name)
    assert installed.returncode == 0, installed.stderr
    assert destination.read_bytes() == plugins._src_bytes(plugin.files[0].src)
    state, _ = plugins._load_state(root, plugin)
    assert state["directories"][plugin.cleanup_dirs[0]]["identity"]

    removed = _rust_plugin_uninstall(plugin.name)
    assert removed.returncode == 0, removed.stderr
    assert "removed (empty directory)" in removed.stdout
    assert not destination.exists()
    assert not cleanup_directory.exists()
    assert not plugins._state_path(root, plugin).exists()


@pytest.mark.parametrize(
    ("adopt", "expected_disposition", "expected_result", "preserved"),
    [
        (False, "preexisting", "skipped (identical pre-existing file; will be preserved)", True),
        (True, "created", "adopted identical legacy installation (managed)", False),
    ],
)
def test_rust_plugin_install_matches_python_identical_file_ownership(
    tmp_path, monkeypatch, adopt, expected_disposition, expected_result, preserved
):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_bytes(plugins._src_bytes(plugin.files[0].src))

    options = ("--adopt-identical",) if adopt else ()
    installed = _rust_plugin_install(plugin.name, *options)
    assert installed.returncode == 0, installed.stderr
    assert expected_result in installed.stdout
    state, _ = plugins._load_state(root, plugin)
    assert state["files"][plugin.files[0].dest]["disposition"] == expected_disposition

    removed = _rust_plugin_uninstall(plugin.name)
    assert removed.returncode == 0, removed.stderr
    assert destination.exists() is preserved


def test_rust_plugin_uninstall_preserves_edits_and_clears_missing_files(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest

    assert _rust_plugin_install(plugin.name).returncode == 0
    destination.write_text("user edit", encoding="utf-8")
    preserved = _rust_plugin_uninstall(plugin.name)
    assert preserved.returncode == 0, preserved.stderr
    assert "preserved (not the unchanged managed file)" in preserved.stdout
    assert destination.read_text(encoding="utf-8") == "user edit"
    assert plugin.files[0].dest in plugins._load_state(root, plugin)[0]["files"]

    destination.unlink()
    removed = _rust_plugin_uninstall(plugin.name)
    assert removed.returncode == 0, removed.stderr
    assert "absent" in removed.stdout
    assert not plugins._state_path(root, plugin).exists()


def test_rust_plugin_uninstall_restores_python_backup_and_original_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_text("user file", encoding="utf-8")
    if destination.stat().st_mode & 0o777:
        destination.chmod(0o600)
    original = destination.stat()

    plugins.install(plugin, force=True)
    removed = _rust_plugin_uninstall(plugin.name)
    assert removed.returncode == 0, removed.stderr
    assert "removed (restored backup)" in removed.stdout
    assert destination.read_text(encoding="utf-8") == "user file"
    assert destination.stat().st_ino == original.st_ino
    if destination.stat().st_mode & 0o777:
        assert destination.stat().st_mode & 0o777 == original.st_mode & 0o777
    assert not destination.with_name(destination.name + plugins._BAK_SUFFIX).exists()
    assert not plugins._state_path(root, plugin).exists()


def test_rust_plugin_uninstall_retains_nonempty_cleanup_directory_for_retry(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("claude-code")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    cleanup_directory = root / plugin.cleanup_dirs[0]
    note = cleanup_directory / "NOTES.md"

    assert _rust_plugin_install(plugin.name).returncode == 0
    note.write_text("keep this", encoding="utf-8")
    first = _rust_plugin_uninstall(plugin.name)
    assert first.returncode == 0, first.stderr
    assert "preserved (not empty)" in first.stdout
    assert not destination.exists()
    assert note.read_text(encoding="utf-8") == "keep this"
    assert plugins._load_state(root, plugin)[0]["directories"]

    note.unlink()
    second = _rust_plugin_uninstall(plugin.name)
    assert second.returncode == 0, second.stderr
    assert "removed (empty directory)" in second.stdout
    assert not cleanup_directory.exists()
    assert not plugins._state_path(root, plugin).exists()


def test_rust_plugin_uninstall_removes_python_historical_managed_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / "legacy" / "AGENTS.md"
    destination.parent.mkdir(parents=True)
    destination.write_text("previously managed payload", encoding="utf-8")
    info = destination.stat()
    state_dir = root / ".agentrouter-state"
    state_dir.mkdir(parents=True)
    state = plugins._empty_state(plugin)
    state["state_dir_identity"] = plugins._identity_json(state_dir.stat())
    state["files"]["legacy/AGENTS.md"] = {
        "disposition": "created",
        "installed_sha256": plugins._sha256(destination.read_bytes()),
        "installed_identity": plugins._identity_json(info),
        "backup": None,
    }
    plugins._state_path(root, plugin).write_bytes(plugins._serialized_state(state))

    removed = _rust_plugin_uninstall(plugin.name)
    assert removed.returncode == 0, removed.stderr
    assert "removed" in removed.stdout
    assert not destination.exists()
    assert not plugins._state_path(root, plugin).exists()


def test_rust_plugin_uninstall_recovers_a_completed_python_backup_restore(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_text("original user content", encoding="utf-8")
    plugins.install(plugin, force=True)
    state, _ = plugins._load_state(root, plugin)
    backup = root / state["files"][plugin.files[0].dest]["backup"]

    # Model a crash after link-and-unlink restored the backup but before state
    # was saved: the original inode is back at the destination, while the
    # ownership record still names the now-absent backup.
    destination.unlink()
    plugins._restore_backup(root, backup, destination)
    recovered = _rust_plugin_uninstall(plugin.name)
    assert recovered.returncode == 0, recovered.stderr
    assert "recovered completed backup restoration" in recovered.stdout
    assert destination.read_text(encoding="utf-8") == "original user content"
    assert not plugins._state_path(root, plugin).exists()


def test_rust_plugin_uninstall_preserves_hardlinked_managed_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    outside = tmp_path / "linked-copy"

    assert _rust_plugin_install(plugin.name).returncode == 0
    outside.hardlink_to(destination)
    preserved = _rust_plugin_uninstall(plugin.name)
    assert preserved.returncode == 0, preserved.stderr
    assert "preserved (not the unchanged managed file)" in preserved.stdout
    assert destination.read_bytes() == outside.read_bytes()
    assert plugins._load_state(root, plugin)[0]["files"]


def test_rust_plugin_uninstall_refuses_linked_destination_without_following_it(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    outside = tmp_path / "outside.md"
    outside.write_text("leave unchanged", encoding="utf-8")

    assert _rust_plugin_install(plugin.name).returncode == 0
    destination.unlink()
    try:
        destination.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    refused = _rust_plugin_uninstall(plugin.name)
    assert refused.returncode != 0
    assert outside.read_text(encoding="utf-8") == "leave unchanged"
    assert destination.is_symlink()
    persisted = json.loads(plugins._state_path(root, plugin).read_text(encoding="utf-8"))
    assert persisted["files"]


def test_rust_plugin_force_install_preserves_python_backup_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(tmp_path.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_text("user-authored guidance", encoding="utf-8")

    refused = _rust_plugin_install(plugin.name)
    assert refused.returncode != 0
    assert "exists and differs" in refused.stderr
    forced = _rust_plugin_install(plugin.name, "--force")
    assert forced.returncode == 0, forced.stderr
    assert "replaced (backup:" in forced.stdout
    assert destination.read_bytes() == plugins._src_bytes(plugin.files[0].src)
    backup = destination.with_name(destination.name + plugins._BAK_SUFFIX)
    assert backup.read_text(encoding="utf-8") == "user-authored guidance"
    state = plugins._load_state(root, plugin)[0]
    entry = state["files"][plugin.files[0].dest]
    assert entry["disposition"] == "replaced"
    assert entry["backup_identity"] == plugins._identity_json(backup.stat())
    assert entry["backup_mode"] == backup.stat().st_mode & 0o777
    removed = plugins.uninstall(plugin)
    assert any("removed (restored backup)" == item["result"] for item in removed)
    assert destination.read_text(encoding="utf-8") == "user-authored guidance"
    assert not backup.exists()


def test_rust_plugin_install_upgrades_managed_payload_and_preserves_original_backup(
    tmp_path, monkeypatch
):
    plugin = plugins.get_plugin("codex")
    destination_relative = plugin.files[0].dest
    old_payload = b"older AgentRouter-managed payload\n"
    original_payload = b"original user-authored payload\n"

    def prepare(root: Path) -> tuple[Path, Path]:
        destination = root / destination_relative
        destination.parent.mkdir(parents=True)
        destination.write_bytes(old_payload)
        destination_info = destination.stat()
        backup = destination.with_name(destination.name + plugins._BAK_SUFFIX)
        backup.write_bytes(original_payload)
        backup_info = backup.stat()
        state = plugins._empty_state(plugin)
        state["files"][destination_relative] = {
            "disposition": "replaced",
            "installed_sha256": plugins._sha256(old_payload),
            "installed_identity": plugins._identity_json(destination_info),
            "backup": f"{destination_relative}{plugins._BAK_SUFFIX}",
            "backup_sha256": plugins._sha256(original_payload),
            "backup_identity": plugins._identity_json(backup_info),
            "backup_mode": backup_info.st_mode & 0o777,
        }
        plugins._save_state(root, plugin, state)
        return destination, backup

    python_home = (tmp_path / "python-home").resolve()
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(python_home))
    python_root = plugins.dest_root(plugin)
    python_destination, python_backup = prepare(python_root)
    python_result = plugins.install(plugin)

    rust_home = (tmp_path / "rust-home").resolve()
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(rust_home))
    rust_root = plugins.dest_root(plugin)
    rust_destination, rust_backup = prepare(rust_root)
    rust_result = _rust_plugin_install(plugin.name)

    assert rust_result.returncode == 0, rust_result.stderr
    assert "updated (managed payload)" in python_result[0]["result"]
    assert "updated (managed payload)" in rust_result.stdout
    expected = plugins._src_bytes(plugin.files[0].src)
    assert python_destination.read_bytes() == expected
    assert rust_destination.read_bytes() == expected
    assert python_backup.read_bytes() == rust_backup.read_bytes() == original_payload

    python_entry = plugins._load_state(python_root, plugin)[0]["files"][destination_relative]
    rust_entry = plugins._load_state(rust_root, plugin)[0]["files"][destination_relative]
    for entry, backup in (
        (python_entry, python_backup),
        (rust_entry, rust_backup),
    ):
        assert entry["disposition"] == "replaced"
        assert entry["installed_sha256"] == plugins._sha256(expected)
        assert entry["backup"] == f"{destination_relative}{plugins._BAK_SUFFIX}"
        assert entry["backup_sha256"] == plugins._sha256(original_payload)
        backup_info = backup.stat()
        assert entry["backup_identity"] == plugins._identity_json(backup_info)
        assert entry["backup_mode"] == backup_info.st_mode & 0o777


def test_rust_plugin_install_refuses_a_linked_state_directory(tmp_path, monkeypatch):
    linked_root = tmp_path / "linked-root"
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(linked_root.resolve()))
    plugin = plugins.get_plugin("codex")
    root = plugins.dest_root(plugin)
    destination = root / plugin.files[0].dest
    destination.parent.mkdir(parents=True)
    destination.write_text("user-authored guidance", encoding="utf-8")

    state_directory = root / ".agentrouter-state"
    outside = tmp_path / "outside-state"
    outside.mkdir()
    try:
        state_directory.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    blocked = _rust_plugin_install(plugin.name)
    assert blocked.returncode != 0
    assert destination.read_text(encoding="utf-8") == "user-authored guidance"
    assert not list(outside.iterdir())
