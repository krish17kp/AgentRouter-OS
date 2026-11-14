"""Direct Python/Rust differential checks for public schema value types."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest
from pydantic import TypeAdapter, ValidationError

from agentrouter.schema import (
    Ability,
    AbilitySource,
    ApprovalLevel,
    ContextBand,
    DeprecationStatus,
    ExecutionMode,
    ExecutionTarget,
    LatencyTier,
    Level,
    ModelEntry,
    OutputType,
    PricingTier,
    Provider,
    ReleaseChannel,
    SnapshotType,
    TaskType,
)

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


SCHEMA_ENUMS = [
    ("task_type", TaskType),
    ("level", Level),
    ("output_type", OutputType),
    ("approval_level", ApprovalLevel),
    ("context_band", ContextBand),
    ("pricing_tier", PricingTier),
    ("latency_tier", LatencyTier),
    ("deprecation_status", DeprecationStatus),
    ("release_channel", ReleaseChannel),
    ("snapshot_type", SnapshotType),
    ("ability_source", AbilitySource),
    ("execution_mode", ExecutionMode),
]


@pytest.mark.parametrize(
    ("kind", "enum_type", "value"),
    [(kind, enum_type, member.value) for kind, enum_type in SCHEMA_ENUMS for member in enum_type],
)
def test_rust_schema_enum_values_match_pydantic(kind, enum_type, value):
    adapter = TypeAdapter(enum_type)
    expected = adapter.dump_python(adapter.validate_python(value), mode="json")
    process = _rust_schema(kind, value)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize(
    ("kind", "enum_type", "value"),
    [
        (kind, enum_type, value)
        for kind, enum_type in SCHEMA_ENUMS
        for value in ("not-a-schema-enum-value", None, 7)
    ],
)
def test_rust_schema_enums_reject_values_pydantic_rejects(kind, enum_type, value):
    with pytest.raises(ValidationError):
        TypeAdapter(enum_type).validate_python(value)
    process = _rust_schema(kind, value)
    assert process.returncode != 0
    assert process.stdout == ""


MODEL_ENTRY_BASE = {
    "provider": "openai",
    "model_id": "gpt-test",
    "context_window": 128000,
    "max_output_tokens": 16384,
    "pricing_tier": "medium",
    "latency_tier": "fast",
    "ability": {"coding": 8, "reasoning": 7, "writing": 6},
    "tool_support": ["function_call"],
    "vision_support": False,
    "deprecation_status": "active",
}


@pytest.mark.parametrize(
    "payload",
    [
        MODEL_ENTRY_BASE,
        {
            **MODEL_ENTRY_BASE,
            "vendor": "model-maker",
            "display_name": "Friendly Model",
        },
        {
            **MODEL_ENTRY_BASE,
            "vendor": None,
            "display_name": "",
            "family": "gpt",
            "release_channel": "preview",
            "snapshot_type": "pinned",
            "context_window": "1000000000000000000000000000000",
            "max_input_tokens": "8192",
            "input_price_per_million": True,
            "output_price_per_million": "0",
            "pricing_basis": "api_list",
            "pricing_effective_date": "2026-11-14",
            "ability_source": "benchmark",
            "ability_confidence": True,
            "vision_support": "yes",
            "audio_support": 1,
            "video_support": False,
            "reasoning_support": "true",
            "ideal_use_cases": ["analysis"],
            "avoid_use_cases": ["unsafe"],
            "deprecation_status": "deprecated",
            "fallback": ["gpt-fallback"],
            "execution_targets": [
                {
                    "host": "openai-api",
                    "host_model_id": "gpt-test",
                    "execution_mode": "api",
                }
            ],
            "notes": "fixture",
            "source": "curated",
            "source_url_or_identifier": "model-card",
            "last_updated": "2026-11-13",
            "last_verified": "2026-11-14",
        },
    ],
)
def test_rust_model_entry_defaults_fields_and_properties_match_pydantic(payload):
    model = ModelEntry.model_validate(payload)
    expected = {
        "model": model.model_dump(mode="json"),
        "properties": {
            "key": model.key,
            "vendor_key": model.vendor_key,
            "name": model.name,
        },
    }
    process = _rust_schema("model_entry", payload)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"context_window": 0},
        {"max_input_tokens": 0},
        {"max_output_tokens": -1},
        {"input_price_per_million": -0.01},
        {"input_price_per_million": "NaN"},
        {"input_price_per_million": "Infinity"},
        {"output_price_per_million": "Infinity"},
        {"output_price_per_million": "-Infinity"},
        {"ability_confidence": -0.01},
        {"ability_confidence": 1.01},
        {"ability_confidence": "NaN"},
        {"ability": {"coding": 11, "reasoning": 7, "writing": 6}},
        {"pricing_tier": "unknown-tier"},
        {"tool_support": [1]},
        {
            "execution_targets": [
                {
                    "host": "openai-api",
                    "host_model_id": "gpt-test",
                    "execution_mode": "shell",
                }
            ]
        },
        {"unknown_field": True},
    ],
)
def test_rust_model_entry_rejects_values_pydantic_rejects(changes):
    payload = {**MODEL_ENTRY_BASE, **changes}
    with pytest.raises(ValidationError):
        ModelEntry.model_validate(payload)
    process = _rust_schema("model_entry", payload)
    assert process.returncode != 0
    assert process.stdout == ""


@pytest.mark.parametrize(
    "missing_field",
    [
        "provider",
        "model_id",
        "context_window",
        "max_output_tokens",
        "pricing_tier",
        "latency_tier",
        "ability",
        "tool_support",
        "vision_support",
        "deprecation_status",
    ],
)
def test_rust_model_entry_rejects_missing_required_fields(missing_field):
    payload = {**MODEL_ENTRY_BASE}
    del payload[missing_field]
    with pytest.raises(ValidationError):
        ModelEntry.model_validate(payload)
    process = _rust_schema("model_entry", payload)
    assert process.returncode != 0
    assert process.stdout == ""
