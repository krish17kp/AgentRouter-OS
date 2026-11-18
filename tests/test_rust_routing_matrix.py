"""Broad differential matrix for the staged Rust scorer against Python."""

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


@pytest.fixture(scope="module")
def models():
    return load_models(SEEDS / "models.yaml", load_providers(SEEDS / "providers.yaml"))[0]


def _rust_route(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-routing", "--bin", "route_from_json"],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


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
def test_rust_route_matches_python_across_dimensions(
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
        "models": [model.model_dump(mode="json") for model in models],
        "classification": cls.model_dump(mode="json"),
        "preference": preference,
    }
    completed = _rust_route(payload)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == route(models, cls, prefer=preference)


def test_unknown_preference_is_rejected_without_output(models):
    cls = Classification(
        task_type=TaskType.general,
        complexity=Level.low,
        risk=Level.low,
        context_tokens=2_000,
        context_band=ContextBand.small,
        output_type=OutputType.text,
        tool_needs=[],
        approval_level=ApprovalLevel.auto,
    )
    completed = _rust_route(
        {
            "models": [model.model_dump(mode="json") for model in models],
            "classification": cls.model_dump(mode="json"),
            "preference": "unknown",
        }
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
