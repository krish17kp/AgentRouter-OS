"""Rust route-control exclusions must match the Python prefilter."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict
from pathlib import Path

import pytest

from agentrouter.controls import RouteControls, apply_controls
from agentrouter.registry import load_models, load_providers

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "agentrouter" / "seeds"
pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


@pytest.fixture(scope="module")
def models():
    return load_models(SEEDS / "models.yaml", load_providers(SEEDS / "providers.yaml"))[0]


@pytest.mark.parametrize(
    "controls",
    [
        RouteControls(),
        RouteControls(vendor=("anthropic",)),
        RouteControls(exclude_vendor=("OpenAI",)),
        RouteControls(model="claude-sonnet-5"),
        RouteControls(host=("claude-code",)),
        RouteControls(exclude_host=("anthropic-api",)),
        RouteControls(max_price=1.0),
        RouteControls(stable_only=True),
        RouteControls(prohibit_tool=("function-calling", "shell")),
        RouteControls(vendor=("anthropic",), prohibit_tool=("web",)),
    ],
)
def test_rust_controls_match_python(models, controls):
    kept, dropped = apply_controls(models, controls)
    payload = {
        "providers_yaml": (SEEDS / "providers.yaml").read_text(encoding="utf-8"),
        "models_yaml": (SEEDS / "models.yaml").read_text(encoding="utf-8"),
        "controls": asdict(controls),
    }
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "-p",
            "agentrouter-policy",
            "--bin",
            "controls_from_registry_json",
        ],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "kept": [model.key for model in kept],
        "dropped": dropped,
    }


def test_available_only_fails_closed_without_host_evidence(models):
    payload = {
        "providers_yaml": (SEEDS / "providers.yaml").read_text(encoding="utf-8"),
        "models_yaml": (SEEDS / "models.yaml").read_text(encoding="utf-8"),
        "controls": {"available_only": True},
    }
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "-p",
            "agentrouter-policy",
            "--bin",
            "controls_from_registry_json",
        ],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    output = json.loads(result.stdout)
    assert output["kept"] == []
    assert len(output["dropped"]) == len(models)
    assert all("no available execution host" in row["reason"] for row in output["dropped"])


def test_available_only_uses_only_explicit_host_evidence(models):
    selected = models[0].key
    payload = {
        "providers_yaml": (SEEDS / "providers.yaml").read_text(encoding="utf-8"),
        "models_yaml": (SEEDS / "models.yaml").read_text(encoding="utf-8"),
        "controls": {"available_only": True},
        "available": {selected: True},
    }
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "-p",
            "agentrouter-policy",
            "--bin",
            "controls_from_registry_json",
        ],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(result.stdout)["kept"] == [selected]
