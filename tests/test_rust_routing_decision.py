"""Python/Rust differential checks for the complete static routing pass."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.engine import route
from agentrouter.registry import load_models, load_providers
from agentrouter.schema import (
    ApprovalLevel,
    Classification,
    ContextBand,
    Level,
    OutputType,
    TaskType,
)

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "agentrouter" / "seeds"
pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROUTING_FIELDS = {
    "provider",
    "model_id",
    "context_window",
    "pricing_tier",
    "latency_tier",
    "ability",
    "tool_support",
    "vision_support",
    "ideal_use_cases",
    "avoid_use_cases",
    "deprecation_status",
    "fallback",
}


@pytest.fixture(scope="module")
def models():
    providers = load_providers(SEEDS / "providers.yaml")
    return load_models(SEEDS / "models.yaml", providers)[0]


@pytest.mark.parametrize("task_type", list(TaskType))
@pytest.mark.parametrize(
    ("complexity", "risk", "context_tokens", "band", "tools", "preference"),
    [
        (Level.low, Level.low, 1_000, ContextBand.small, [], None),
        (Level.high, Level.high, 100_000, ContextBand.large, ["file-edit", "shell"], "quality"),
        (Level.medium, Level.low, 4_000, ContextBand.medium, ["web"], "cheap"),
        (Level.high, Level.medium, 5_000_000, ContextBand.large, ["vision"], None),
        (Level.medium, Level.low, 2_000, ContextBand.small, ["nonexistent-tool"], None),
    ],
)
def test_rust_decision_matches_python(
    models, task_type, complexity, risk, context_tokens, band, tools, preference
):
    cls = Classification(
        task_type=task_type,
        complexity=complexity,
        risk=risk,
        context_tokens=context_tokens,
        context_band=band,
        output_type=OutputType.text,
        tool_needs=tools,
        approval_level=(
            ApprovalLevel.human_approval_required if risk is Level.high else ApprovalLevel.auto
        ),
    )
    payload = {
        "models": [model.model_dump(mode="json", include=ROUTING_FIELDS) for model in models],
        "classification": cls.model_dump(mode="json"),
        "preference": preference,
    }
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-routing", "--bin", "route_from_json"],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    actual = json.loads(completed.stdout)
    expected = route(models, cls, prefer=preference)
    for index, (actual_row, expected_row) in enumerate(
        zip(actual["scores"], expected["scores"], strict=True)
    ):
        assert actual_row == expected_row, (index, actual_row, expected_row)
    assert actual == expected


@pytest.mark.parametrize("task_type", list(TaskType))
def test_rust_registry_to_route_matches_python(models, task_type):
    cls = Classification(
        task_type=task_type,
        complexity=Level.medium,
        risk=Level.low,
        context_tokens=8_000,
        context_band=ContextBand.medium,
        output_type=OutputType.text,
        tool_needs=["tool-use"],
        approval_level=ApprovalLevel.auto,
    )
    payload = {
        "providers_yaml": (SEEDS / "providers.yaml").read_text(encoding="utf-8"),
        "models_yaml": (SEEDS / "models.yaml").read_text(encoding="utf-8"),
        "classification": cls.model_dump(mode="json"),
    }
    completed = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "-p",
            "agentrouter-routing",
            "--bin",
            "route_from_registry_json",
        ],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(completed.stdout) == route(models, cls)
