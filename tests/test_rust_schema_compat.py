"""Direct Python/Rust differential checks for public schema value types."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest
from pydantic import ValidationError

from agentrouter.schema import Ability, ExecutionTarget, Provider

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


def _rust_schema(kind: str, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-registry",
            "--bin",
            "schema_value_from_json",
        ],
        input=json.dumps({"kind": kind, "value": payload}),
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


@pytest.mark.parametrize(
    ("kind", "model", "payload"),
    [
        (
            "execution_target",
            ExecutionTarget,
            {"host": "local", "host_model_id": "small"},
        ),
        (
            "execution_target",
            ExecutionTarget,
            {
                "host": "openai-api",
                "host_model_id": "gpt-test",
                "execution_mode": "api",
                "command_template": ["agentrouter", "{prompt}"],
                "required_command": None,
                "required_env": ["OPENAI_API_KEY"],
                "supports_noninteractive": "n",
                "supports_file_edit": 1,
                "supports_shell": "ON",
            },
        ),
        ("provider", Provider, {"id": "local", "adapter": "manual"}),
        (
            "provider",
            Provider,
            {
                "id": "openai",
                "adapter": "openai-responses",
                "auth_model": "api-key",
                "supports_execution": "yes",
                "exec_command": ["agentrouter", "execute", "{prompt}"],
            },
        ),
    ],
)
def test_rust_schema_defaults_and_coercions_match_pydantic(kind, model, payload):
    expected = model.model_validate(payload).model_dump(mode="json")
    process = _rust_schema(kind, payload)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize(
    ("kind", "model", "payload"),
    [
        (
            "execution_target",
            ExecutionTarget,
            {"host_model_id": "small"},
        ),
        (
            "execution_target",
            ExecutionTarget,
            {"host": "local", "host_model_id": "small", "execution_mode": "shell"},
        ),
        (
            "execution_target",
            ExecutionTarget,
            {"host": "local", "host_model_id": "small", "required_env": "KEY"},
        ),
        (
            "execution_target",
            ExecutionTarget,
            {
                "host": "local",
                "host_model_id": "small",
                "supports_shell": "maybe",
            },
        ),
        (
            "execution_target",
            ExecutionTarget,
            {"host": "local", "host_model_id": "small", "unknown": True},
        ),
        ("provider", Provider, {"adapter": "manual"}),
        ("provider", Provider, {"id": "local", "adapter": "manual", "extra": 1}),
        (
            "provider",
            Provider,
            {"id": "local", "adapter": "manual", "supports_execution": "maybe"},
        ),
        (
            "provider",
            Provider,
            {"id": "local", "adapter": "manual", "exec_command": "agentrouter"},
        ),
    ],
)
def test_rust_schema_rejects_values_pydantic_rejects(kind, model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)
    process = _rust_schema(kind, payload)
    assert process.returncode != 0
    assert process.stdout == ""
