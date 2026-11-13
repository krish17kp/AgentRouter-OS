"""Differential checks for the Rust plugin manifest and path-safety slice."""

import json
import subprocess
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
