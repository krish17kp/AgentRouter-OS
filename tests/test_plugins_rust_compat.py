"""Differential checks for the Rust plugin manifest and path-safety slice."""

import json
import subprocess
from pathlib import Path

from agentrouter import plugins


def _rust_plugin_probe(payload: dict) -> dict:
    repository = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "plugin_paths_from_json",
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
