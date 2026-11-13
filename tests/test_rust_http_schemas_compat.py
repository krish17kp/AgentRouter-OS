"""Python/Rust request-schema differential tests for the HTTP contract."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentrouter.server.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    DecisionResponse,
    DryRunRequest,
    DryRunResponse,
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    HostStatusResponse,
    ModelSummary,
    RouteRequest,
    RouteResponse,
)

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _rust(kind: str, request: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-api",
            "--bin",
            "api_request_from_json",
        ],
        input=json.dumps({"kind": kind, "request": request}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


def _rust_response(kind: str, response: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-api",
            "--bin",
            "api_response_from_json",
        ],
        input=json.dumps({"kind": kind, "response": response}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize(
    ("kind", "model", "payload"),
    [
        (
            "classify",
            ClassifyRequest,
            {
                "task": "review this code",
                "context_tokens": 2048,
                "risk": "high",
                "tools": ["filesystem"],
            },
        ),
        (
            "route",
            RouteRequest,
            {
                "task": "summarize a report",
                "context_tokens": None,
                "risk": None,
                "tools": None,
                "prefer": "openai/gpt-4.1",
                "no_log": False,
            },
        ),
        (
            "feedback",
            FeedbackRequest,
            {"decision_id": "d_abc123", "rating": 4, "note": "useful ✓"},
        ),
        ("dry_run", DryRunRequest, {"decision_id": "d_abc123"}),
    ],
)
def test_rust_http_request_schema_roundtrips_like_python(kind, model, payload):
    expected = model.model_validate(payload).model_dump(mode="json")
    process = _rust(kind, {**payload, "ignored_extra": "Python ignores this"})
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize(
    ("kind", "model", "payload"),
    [
        ("classify", ClassifyRequest, {"task": ""}),
        ("classify", ClassifyRequest, {"task": "task", "context_tokens": 0}),
        ("classify", ClassifyRequest, {"task": "task", "tools": ["tool"] * 101}),
        (
            "route",
            RouteRequest,
            {"task": "task", "prefer": "p" * 201},
        ),
        ("feedback", FeedbackRequest, {"decision_id": "", "rating": 3}),
        ("feedback", FeedbackRequest, {"decision_id": "d_1", "rating": 6}),
        (
            "feedback",
            FeedbackRequest,
            {"decision_id": "d_1", "rating": 3, "note": "n" * 10_001},
        ),
        ("dry_run", DryRunRequest, {"decision_id": ""}),
        ("dry_run", DryRunRequest, {"decision_id": "d" * 201}),
    ],
)
def test_rust_http_request_schema_rejects_python_invalid_values(kind, model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)
    process = _rust(kind, payload)
    assert process.returncode != 0
    assert process.stdout == ""


@pytest.mark.parametrize(
    ("kind", "model", "payload"),
    [
        (
            "error",
            ErrorResponse,
            {"error": {"code": "internal_error", "message": "request failed"}},
        ),
        ("health", HealthResponse, {"status": "ok"}),
        (
            "model",
            ModelSummary,
            {
                "vendor": "openai",
                "model_id": "gpt-4.1",
                "key": "openai/gpt-4.1",
                "release_channel": "stable",
                "context_window": "128000",
                "host_availability": "available",
                "ignored_extra": "Pydantic ignores extra fields",
            },
        ),
        (
            "host",
            HostStatusResponse,
            {"host": "local", "availability": "available", "reason": "ready"},
        ),
        (
            "feedback",
            FeedbackResponse,
            {"decision_id": "d_1", "recorded": "yes"},
        ),
        (
            "classify",
            ClassifyResponse,
            {"task_type": {"raw": [1, None]}, "runtime_field": {"kept": True}},
        ),
        (
            "route",
            RouteResponse,
            {"scores": [{"model": "a", "score": 0.7}], "runtime_field": 17},
        ),
        (
            "decision",
            DecisionResponse,
            {"created_at": {"legacy": True}, "user": ["opaque"], "runtime_field": 2},
        ),
        (
            "dry_run",
            DryRunResponse,
            {"argv": {"historical": "shape"}, "runtime_field": ["kept"]},
        ),
    ],
)
def test_rust_http_response_schema_roundtrips_like_python(kind, model, payload):
    expected = model.model_validate(payload).model_dump(mode="json")
    process = _rust_response(kind, payload)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("classify", {"task": "x", "context_tokens": True}),
        ("classify", {"task": "x", "context_tokens": 3.0}),
        ("classify", {"task": "x", "context_tokens": "1_000"}),
        ("classify", {"task": "x", "context_tokens": "12.0"}),
        ("route", {"task": "x", "no_log": "yes"}),
        ("route", {"task": "x", "no_log": 0.0}),
        ("feedback", {"decision_id": "d_1", "rating": True}),
        ("feedback", {"decision_id": "d_1", "rating": 4.0}),
        ("feedback", {"decision_id": "d_1", "rating": "5.0"}),
    ],
)
def test_rust_http_request_schema_matches_supported_pydantic_coercions(kind, payload):
    model = {
        "classify": ClassifyRequest,
        "route": RouteRequest,
        "feedback": FeedbackRequest,
    }[kind]
    expected = model.model_validate(payload).model_dump(mode="json")
    process = _rust(kind, payload)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("classify", {"task": "x", "context_tokens": 2.5}),
        ("classify", {"task": "x", "context_tokens": "1e3"}),
        ("route", {"task": "x", "no_log": "sometimes"}),
        ("feedback", {"decision_id": "d_1", "rating": 1.5}),
    ],
)
def test_rust_http_request_schema_rejects_invalid_pydantic_coercions(kind, payload):
    model = {
        "classify": ClassifyRequest,
        "route": RouteRequest,
        "feedback": FeedbackRequest,
    }[kind]
    with pytest.raises(ValidationError):
        model.model_validate(payload)
    process = _rust(kind, payload)
    assert process.returncode != 0
    assert process.stdout == ""
