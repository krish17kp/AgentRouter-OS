"""Cross-language parity for the first isolated Rust routing policy slice."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.engine import weights_for
from agentrouter.schema import (
    ApprovalLevel,
    Classification,
    ContextBand,
    Level,
    OutputType,
    TaskType,
)

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


@pytest.mark.parametrize(
    ("complexity", "risk", "band", "preference"),
    [
        (Level.medium, Level.low, ContextBand.small, None),
        (Level.low, Level.low, ContextBand.small, None),
        (Level.low, Level.high, ContextBand.large, None),
        (Level.high, Level.low, ContextBand.large, None),
        (Level.medium, Level.low, ContextBand.large, None),
        (Level.high, Level.high, ContextBand.large, "quality"),
        (Level.low, Level.low, ContextBand.small, "cheap"),
        (Level.medium, Level.high, ContextBand.large, "fast"),
        (Level.high, Level.low, ContextBand.large, "balanced"),
    ],
)
def test_rust_weight_policy_matches_python(complexity, risk, band, preference):
    classification = Classification(
        task_type=TaskType.coding,
        complexity=complexity,
        risk=risk,
        context_tokens=100,
        context_band=band,
        output_type=OutputType.code,
        tool_needs=[],
        approval_level=ApprovalLevel.auto,
    )
    expected_weights, expected_shifts = weights_for(classification, prefer=preference)
    request = {"classification": classification.model_dump(mode="json"), "preference": preference}
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-routing", "--bin", "weights_from_json"],
        cwd=ROOT,
        input=json.dumps(request),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(completed.stdout) == {
        "weights": expected_weights,
        "shifts": expected_shifts,
    }


def test_rust_weight_policy_rejects_unknown_preference():
    classification = Classification(
        task_type=TaskType.general,
        complexity=Level.medium,
        risk=Level.low,
        context_tokens=100,
        context_band=ContextBand.small,
        output_type=OutputType.text,
        tool_needs=[],
        approval_level=ApprovalLevel.auto,
    )
    request = {"classification": classification.model_dump(mode="json"), "preference": "unsafe"}
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-routing", "--bin", "weights_from_json"],
        cwd=ROOT,
        input=json.dumps(request),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode != 0
    assert completed.stdout == ""


def test_rust_custom_base_matches_python_with_context_shift():
    classification = Classification(
        task_type=TaskType.analysis,
        complexity=Level.medium,
        risk=Level.low,
        context_tokens=300_000,
        context_band=ContextBand.large,
        output_type=OutputType.text,
        tool_needs=[],
        approval_level=ApprovalLevel.notify,
    )
    base = {"w_cap": 0.1, "w_cost": 0.2, "w_lat": 0.3, "w_ctx": 0.4}
    expected_weights, expected_shifts = weights_for(classification, base=base)
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-routing", "--bin", "weights_from_json"],
        cwd=ROOT,
        input=json.dumps({"classification": classification.model_dump(mode="json"), "base": base}),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(completed.stdout) == {
        "weights": expected_weights,
        "shifts": expected_shifts,
    }
