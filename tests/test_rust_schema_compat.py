"""Direct Python/Rust differential checks for public schema value types."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest
from pydantic import ValidationError

from agentrouter.schema import Ability

ROOT = os.path.dirname(os.path.dirname(__file__))
pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _rust_ability(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-registry",
            "--bin",
            "ability_from_json",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "CARGO_BUILD_JOBS": "1",
            "CARGO_PROFILE_DEV_DEBUG": "0",
            "CARGO_INCREMENTAL": "0",
        },
        cwd=ROOT,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"coding": 0, "reasoning": 5, "writing": 10},
        {"coding": True, "reasoning": False, "writing": 1.0},
        {"coding": " 2 ", "reasoning": "1_0", "writing": "0"},
        {"coding": 1e1, "reasoning": 2.0, "writing": -0.0},
    ],
)
def test_rust_ability_roundtrip_matches_pydantic(payload):
    expected = Ability.model_validate(payload).model_dump(mode="json")
    process = _rust_ability(payload)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"coding": -1, "reasoning": 0, "writing": 0},
        {"coding": 11, "reasoning": 0, "writing": 0},
        {"coding": 1.5, "reasoning": 0, "writing": 0},
        {"coding": "not-a-score", "reasoning": 0, "writing": 0},
        {"coding": 0, "reasoning": 0, "writing": 0, "extra": 1},
        {"coding": 0, "reasoning": 0},
    ],
)
def test_rust_ability_rejects_values_pydantic_rejects(payload):
    with pytest.raises(ValidationError):
        Ability.model_validate(payload)
    process = _rust_ability(payload)
    assert process.returncode != 0
    assert process.stdout == ""
