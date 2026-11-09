"""Risk and approval gates must match Python before a Rust adapter can execute."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.safety import gates_for
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


@pytest.mark.parametrize("risk", list(Level))
@pytest.mark.parametrize("approval", list(ApprovalLevel))
def test_rust_safety_gates_match_python(risk, approval):
    cls = Classification(
        task_type=TaskType.coding,
        complexity=Level.medium,
        risk=risk,
        context_tokens=1200,
        context_band=ContextBand.small,
        output_type=OutputType.code,
        tool_needs=[],
        approval_level=approval,
    )
    completed = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-routing", "--bin", "safety_from_json"],
        cwd=ROOT,
        input=cls.model_dump_json(),
        text=True,
        capture_output=True,
        timeout=120,
        check=True,
    )
    assert json.loads(completed.stdout) == gates_for(cls)
