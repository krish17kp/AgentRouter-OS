"""Python/Rust JSON-contract compatibility check for the R1 milestone.

Builds the same `Classification` values on both sides and asserts the JSON
is identical, proving `agentrouter-core`'s serde contract matches
`agentrouter.schema.Classification` byte-for-byte (field names, enum string
values, field order is irrelevant since we compare as dicts).

Skips (does not fail) when `cargo` isn't on PATH, since Rust is optional
tooling for anyone just working on the Python implementation.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from agentrouter.schema import (
    ApprovalLevel,
    Classification,
    ContextBand,
    Level,
    OutputType,
    TaskType,
)

RUST_CRATE_DIR = "rust/agentrouter-core"

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _python_classification_json() -> dict:
    c = Classification(
        task_type=TaskType.coding,
        complexity=Level.medium,
        risk=Level.low,
        context_tokens=1200,
        context_band=ContextBand.small,
        output_type=OutputType.code_tests,
        tool_needs=["filesystem"],
        approval_level=ApprovalLevel.human_approval_required,
    )
    return json.loads(c.model_dump_json())


def _rust_classification_json() -> dict:
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "print_classification"],
        cwd=RUST_CRATE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(result.stdout.strip())


def test_classification_json_matches_between_python_and_rust():
    assert _rust_classification_json() == _python_classification_json()
