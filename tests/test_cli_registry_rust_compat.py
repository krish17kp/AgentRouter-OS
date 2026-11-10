"""Rust `registry list` probe matches the Python CLI on the same home."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from agentrouter.cli import app

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
runner = CliRunner()


@pytest.fixture
def seeded_home(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    monkeypatch.setenv("AGENTROUTER_HOME", str(home))
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    return home


def _rust_registry(home, *options):
    return subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "registry_cli", "--", str(home), *options],
        cwd="rust/agentrouter-cli",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize(
    "options",
    [
        ("--json",),
        ("--provider", "openai", "--json"),
        ("--provider", "no-such-provider", "--json"),
        ("--active-only", "--json"),
    ],
)
def test_rust_registry_json_matches_python(seeded_home, options):
    python = runner.invoke(app, ["registry", "list", *options])
    rust = _rust_registry(seeded_home, *options)
    assert python.exit_code == rust.returncode == 0
    assert json.loads(rust.stdout) == json.loads(python.stdout)


@pytest.mark.parametrize("options", [(), ("--provider", "openai"), ("--active-only",)])
def test_rust_registry_table_matches_python(seeded_home, options):
    python = runner.invoke(app, ["registry", "list", *options])
    rust = _rust_registry(seeded_home, *options)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout


def test_rust_registry_active_filter_removes_deprecated_model(seeded_home):
    path = seeded_home / "registry" / "models.yaml"
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original.replace("deprecation_status: active", "deprecation_status: deprecated", 1)
    )
    python = runner.invoke(app, ["registry", "list", "--active-only", "--json"])
    rust = _rust_registry(seeded_home, "--active-only", "--json")
    assert python.exit_code == rust.returncode == 0
    assert json.loads(rust.stdout) == json.loads(python.stdout)
    assert len(json.loads(rust.stdout)) == 7


def test_rust_registry_rejects_invalid_registry(seeded_home):
    (seeded_home / "registry" / "providers.yaml").write_text("[not, a, mapping]\n")
    rust = _rust_registry(seeded_home, "--json")
    assert rust.returncode == 3
    assert rust.stdout == ""


@pytest.mark.parametrize(
    "old,new",
    [
        ("ability_confidence: 0.4", "ability_confidence: .nan"),
        ("ability_confidence: 0.4", "ability_confidence: 1.5"),
        ("context_window: 1000000", "context_window: 0"),
        ("max_output_tokens: 128000", "max_output_tokens: 0"),
        ("ability: { coding: 9", "ability: { coding: 11"),
        (
            "pricing_tier: frontier",
            "pricing_tier: frontier\n    input_price_per_million: -1",
        ),
        ('last_updated: "2026-07-14"', "last_updated: bad-date"),
    ],
)
def test_rust_registry_rejects_model_fields_python_rejects(seeded_home, old, new):
    path = seeded_home / "registry" / "models.yaml"
    original = path.read_text(encoding="utf-8")
    assert old in original
    path.write_text(original.replace(old, new, 1), encoding="utf-8")
    python = runner.invoke(app, ["registry", "list", "--json"])
    rust = _rust_registry(seeded_home, "--json")
    assert python.exit_code == rust.returncode == 3
    assert python.stdout == rust.stdout == ""


@pytest.mark.parametrize("options", [("--unknown",), ("--provider",), ("--provider", "--json")])
def test_rust_registry_rejects_unknown_options(seeded_home, options):
    rust = _rust_registry(seeded_home, *options)
    assert rust.returncode == 2
    assert rust.stdout == ""
