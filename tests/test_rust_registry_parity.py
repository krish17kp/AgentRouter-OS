"""Offline Rust registry load must preserve Python's model and warning inventory."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from agentrouter.registry import load_models, load_providers

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "agentrouter" / "seeds"
pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _rust_registry(models_yaml: str, providers_yaml: str):
    return subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-registry", "--bin", "registry_from_json"],
        cwd=ROOT,
        input=json.dumps({"models_yaml": models_yaml, "providers_yaml": providers_yaml}),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def test_seed_registry_matches_python():
    providers_path = SEEDS / "providers.yaml"
    models_path = SEEDS / "models.yaml"
    providers = load_providers(providers_path)
    models, warnings = load_models(models_path, providers)
    result = _rust_registry(
        models_path.read_text(encoding="utf-8"),
        providers_path.read_text(encoding="utf-8"),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "keys": [model.key for model in models],
        "vendors": [model.vendor for model in models],
        "warnings": warnings,
    }


@pytest.mark.parametrize("mutation", ["unknown_field", "zero_context", "unknown_provider"])
def test_registry_rejects_invalid_model(mutation):
    model = {
        "provider": "p",
        "model_id": "m",
        "context_window": 100,
        "max_output_tokens": 10,
        "pricing_tier": "low",
        "latency_tier": "fast",
        "ability": {"coding": 7, "reasoning": 7, "writing": 7},
        "tool_support": [],
        "vision_support": False,
        "deprecation_status": "active",
    }
    if mutation == "unknown_field":
        model["invented"] = True
    elif mutation == "zero_context":
        model["context_window"] = 0
    else:
        model["provider"] = "missing"
    import yaml

    result = _rust_registry(
        yaml.safe_dump({"models": [model]}),
        yaml.safe_dump({"providers": [{"id": "p", "adapter": "p"}]}),
    )
    assert result.returncode != 0
    assert result.stdout == ""


def test_generated_catalog_and_ability_override_match_python(tmp_path):
    import yaml

    base = {
        "provider": "p",
        "model_id": "manual",
        "context_window": 1000,
        "max_output_tokens": 100,
        "pricing_tier": "low",
        "latency_tier": "fast",
        "ability": {"coding": 6, "reasoning": 5, "writing": 4},
        "tool_support": [],
        "vision_support": False,
        "deprecation_status": "active",
    }
    generated = {
        **base,
        "model_id": "generated",
        "ability": {"coding": 3, "reasoning": 4, "writing": 5},
    }
    manual_yaml = yaml.safe_dump({"models": [base]})
    generated_yaml = yaml.safe_dump({"models": [generated, base]})
    overrides_yaml = yaml.safe_dump(
        {"overrides": {"p/manual": {"coding": 9}, "unknown": {"writing": 7}}}
    )
    providers_yaml = yaml.safe_dump({"providers": [{"id": "p", "adapter": "p"}]})
    (tmp_path / "models.yaml").write_text(manual_yaml, encoding="utf-8")
    (tmp_path / "models.a.generated.yaml").write_text(generated_yaml, encoding="utf-8")
    (tmp_path / "ability_overrides.yaml").write_text(overrides_yaml, encoding="utf-8")
    providers = load_providers(_write_providers(tmp_path, providers_yaml))
    from agentrouter.registry import load_all_models

    models, warnings = load_all_models(tmp_path, providers)
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "-p",
            "agentrouter-registry",
            "--bin",
            "registry_merge_from_json",
        ],
        cwd=ROOT,
        input=json.dumps(
            {
                "providers_yaml": providers_yaml,
                "manual_yaml": manual_yaml,
                "generated": [["models.a.generated.yaml", generated_yaml]],
                "overrides_yaml": overrides_yaml,
                "today": date.today().isoformat(),
            }
        ),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "keys": [model.key for model in models],
        "abilities": [[m.ability.coding, m.ability.reasoning, m.ability.writing] for m in models],
        "warnings": warnings,
    }


def test_seed_staleness_warning_matches_python(tmp_path):
    from agentrouter.registry import load_all_models

    providers_yaml = (SEEDS / "providers.yaml").read_text(encoding="utf-8")
    manual_yaml = (SEEDS / "models.yaml").read_text(encoding="utf-8")
    (tmp_path / "providers.yaml").write_text(providers_yaml, encoding="utf-8")
    (tmp_path / "models.yaml").write_text(manual_yaml, encoding="utf-8")
    models, warnings = load_all_models(tmp_path, load_providers(tmp_path / "providers.yaml"))
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "-p",
            "agentrouter-registry",
            "--bin",
            "registry_merge_from_json",
        ],
        cwd=ROOT,
        input=json.dumps(
            {
                "providers_yaml": providers_yaml,
                "manual_yaml": manual_yaml,
                "generated": [],
                "overrides_yaml": None,
                "today": date.today().isoformat(),
            }
        ),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "keys": [model.key for model in models],
        "abilities": [[m.ability.coding, m.ability.reasoning, m.ability.writing] for m in models],
        "warnings": warnings,
    }


def _write_providers(directory, text):
    path = directory / "providers.yaml"
    path.write_text(text, encoding="utf-8")
    return path
