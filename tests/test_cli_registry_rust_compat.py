"""Rust `registry list` probe matches the Python CLI on the same home."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import date

import pytest
import yaml
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
        original.replace("deprecation_status: active", "deprecation_status: deprecated", 1),
        encoding="utf-8",
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


def test_generated_catalog_symlink_is_rejected_by_python_and_rust(seeded_home, tmp_path):
    outside = tmp_path / "outside.yaml"
    outside.write_text("models: []\n", encoding="utf-8")
    try:
        os.symlink(outside, seeded_home / "registry" / "models.other.generated.yaml")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    python = runner.invoke(app, ["registry", "list", "--json"])
    rust = _rust_registry(seeded_home, "--json")
    assert python.exit_code == rust.returncode == 3
    assert rust.stdout == ""


def test_duplicate_registry_keys_are_rejected_by_python_and_rust(seeded_home):
    path = seeded_home / "registry" / "models.other.generated.yaml"
    path.write_text("models: []\nmodels: []\n", encoding="utf-8")
    python = runner.invoke(app, ["registry", "list", "--json"])
    rust = _rust_registry(seeded_home, "--json")
    assert python.exit_code == rust.returncode == 3
    assert rust.stdout == ""


@pytest.mark.parametrize(
    "old,new",
    [
        ("ability_confidence: 0.4", "ability_confidence: .nan"),
        ("ability_confidence: 0.4", "ability_confidence: 1.5"),
        ("context_window: 1000000", "context_window: 0"),
        ("context_window: 1000000", 'context_window: "1.5"'),
        ("context_window: 1000000", 'context_window: "1e3"'),
        ("max_output_tokens: 128000", "max_output_tokens: 0"),
        ("ability: { coding: 9", "ability: { coding: 11"),
        ("ability: { coding: 9", 'ability: { coding: "10.5"'),
        ("vision_support: true", 'vision_support: "maybe"'),
        ("vision_support: true", 'vision_support: " true "'),
        ("vision_support: true", 'vision_support: " 1 "'),
        (
            "pricing_tier: frontier",
            "pricing_tier: frontier\n    input_price_per_million: -1",
        ),
        (
            "pricing_tier: frontier",
            'pricing_tier: frontier\n    input_price_per_million: "not-a-number"',
        ),
        ('last_updated: "2026-07-14"', "last_updated: bad-date"),
        (
            'last_updated: "2026-07-14"',
            'last_updated: "2026-07-14T00:00:01Z"',
        ),
        ('last_updated: "2026-07-14"', "last_updated: 1767225600.1"),
        ('last_updated: "2026-07-14"', "last_updated: true"),
        (
            'last_updated: "2026-07-14"',
            'last_updated: "2026-07-14T00:00:00+0:530"',
        ),
        (
            'last_updated: "2026-07-14"',
            'last_updated: "2026-07-14T😀+00:00"',
        ),
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


@pytest.mark.parametrize(
    "field,date_value",
    [
        (field, value)
        for field in ("pricing_effective_date", "last_updated", "last_verified")
        for value in (
            date(2026, 1, 1),
            "2026-01-01T00:00:00Z",
            "2026-01-01t00:00+05:30",
            "2026-01-01_00:00:00,0z",
            "2026-01-01T00:00:00+0530",
            1767225600,
            1767225600.0,
            "1767225600",
        )
    ],
)
def test_rust_registry_normalizes_pydantic_accepted_dates(seeded_home, field, date_value):
    path = seeded_home / "registry" / "models.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document["models"][0][field] = date_value
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    python = runner.invoke(app, ["registry", "list", "--json"])
    rust = _rust_registry(seeded_home, "--json")
    assert python.exit_code == rust.returncode == 0
    assert json.loads(rust.stdout) == json.loads(python.stdout)


@pytest.mark.parametrize(
    "field,value",
    [
        ("context_window", "1000000"),
        ("context_window", 1000000.0),
        ("context_window", True),
        ("max_input_tokens", "8192.0"),
        ("max_output_tokens", "128000"),
        ("ability.coding", "9.0"),
        ("ability.reasoning", True),
        ("ability.writing", 10.0),
        ("input_price_per_million", "0.125"),
        ("output_price_per_million", True),
        ("ability_confidence", True),
        ("vision_support", "yes"),
        ("audio_support", "OFF"),
        ("video_support", 1.0),
        ("reasoning_support", 0),
    ],
)
def test_rust_registry_coerces_model_scalars_like_pydantic(seeded_home, field, value):
    path = seeded_home / "registry" / "models.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    model = document["models"][0]
    if field.startswith("ability."):
        model["ability"][field.split(".", 1)[1]] = value
    else:
        model[field] = value
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    python = runner.invoke(app, ["registry", "list", "--json"])
    rust = _rust_registry(seeded_home, "--json")
    assert python.exit_code == rust.returncode == 0
    assert json.loads(rust.stdout) == json.loads(python.stdout)


def test_rust_registry_coerces_provider_and_execution_target_booleans(seeded_home):
    providers_path = seeded_home / "registry" / "providers.yaml"
    providers = yaml.safe_load(providers_path.read_text(encoding="utf-8"))
    providers["providers"][0]["supports_execution"] = "yes"
    providers_path.write_text(yaml.safe_dump(providers, sort_keys=False), encoding="utf-8")

    models_path = seeded_home / "registry" / "models.yaml"
    models = yaml.safe_load(models_path.read_text(encoding="utf-8"))
    models["models"][0]["execution_targets"] = [
        {
            "host": "openai-api",
            "host_model_id": "gpt-test",
            "supports_noninteractive": "n",
            "supports_file_edit": 1,
            "supports_shell": "ON",
        }
    ]
    models_path.write_text(yaml.safe_dump(models, sort_keys=False), encoding="utf-8")

    python = runner.invoke(app, ["registry", "list", "--json"])
    rust = _rust_registry(seeded_home, "--json")
    assert python.exit_code == rust.returncode == 0
    assert json.loads(rust.stdout) == json.loads(python.stdout)


@pytest.mark.parametrize("options", [("--unknown",), ("--provider",), ("--provider", "--json")])
def test_rust_registry_rejects_unknown_options(seeded_home, options):
    rust = _rust_registry(seeded_home, *options)
    assert rust.returncode == 2
    assert rust.stdout == ""
