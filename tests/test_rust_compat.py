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
from pydantic import ValidationError

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


def test_classification_schema_roundtrip_and_extra_field_rejection_match():
    payload = _python_classification_json()
    valid = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "classification_from_json"],
        cwd=RUST_CRATE_DIR,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert valid.returncode == 0, valid.stderr
    assert json.loads(valid.stdout) == payload

    invalid = {**payload, "unknown_field": True}
    with pytest.raises(ValidationError):
        Classification.model_validate(invalid)
    rejected = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "classification_from_json"],
        cwd=RUST_CRATE_DIR,
        input=json.dumps(invalid),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert rejected.returncode != 0
    assert rejected.stdout == ""


@pytest.mark.parametrize(
    "confidence,needs_clarification",
    [
        (0.4, False),
        ("0.5", "yes"),
        (True, 0),
        (False, 1.0),
        ("0.0_5", "off"),
        (" 0.5 ", "no"),
        (-0.0, -0.0),
    ],
)
def test_classification_pydantic_scalar_coercions_match(confidence, needs_clarification):
    payload = _python_classification_json()
    payload["confidence"] = confidence
    payload["needs_clarification"] = needs_clarification
    expected = Classification.model_validate(payload).model_dump(mode="json")
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "classification_from_json"],
        cwd=RUST_CRATE_DIR,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("confidence", -0.1),
        ("confidence", 1.1),
        ("confidence", "NaN"),
        ("confidence", "not-a-number"),
        ("confidence", " 0.0_5 "),
        ("needs_clarification", 2),
        ("needs_clarification", 0.5),
        ("needs_clarification", " true "),
        ("needs_clarification", "maybe"),
    ],
)
def test_classification_rejects_pydantic_invalid_scalar_values(field, value):
    payload = _python_classification_json()
    payload[field] = value
    with pytest.raises(ValidationError):
        Classification.model_validate(payload)
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "classification_from_json"],
        cwd=RUST_CRATE_DIR,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode != 0
    assert result.stdout == ""
