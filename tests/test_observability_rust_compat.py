"""Differential tests for the shared Python/Rust secret-safe text helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest

from agentrouter import observability

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def test_redaction_and_safe_echo_match_python_contract():
    secrets = [
        "sk-livekey0123456789abcdef",
        "sk_live_51H8xYzAbCdEfGhIj",
        "github_pat_11ABCDEFG0aBcDeFgHiJkLmN",
        "ghp_0123456789abcdefghijklmnop",
        "glpat-ABCDEFghijkl1234567890",
        "xoxb-1234567890-abcdefghij",
        "hf_ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P",
        "AKIAIOSFODNN7EXAMPLE",
        "ASIAIOSFODNN7EXAMPLE",
        "Bearer eyJhbGciOiJIUzI1NiJ9.abcdefgh.signature",
        "Basic dXNlcjpwYXNzd29yZA==",
        "postgres://user:hunter2@db.internal:5432/x",
        "postgres://user:allletters@db.internal/x",
        "provider/ABCDEFGHIJKLMNOPQRSTUVWXabcdefghijklm",
        'password="hunter2secret"',
        "api_key: AbC123dEf456",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY1",
        "/media/krish/Projects/Agentrouteros/agentrouter/server/app.py",
        "Registry file not found: providers.yaml (run: agentrouter init)",
    ]
    echo_inputs = [
        {"text": "before\nafter\u202e", "limit": 64},
        {"text": "x" * 70, "limit": 64},
        {"text": "a\u200bb\u2028c", "limit": 64},
        {"text": "abcdef", "limit": 0},
        {
            "text": "before"
            + "".join(
                chr(codepoint)
                for codepoint in range(0x110000)
                if unicodedata.category(chr(codepoint)) in {"Cc", "Cf"}
                or codepoint in {0x2028, 0x2029}
            )
            + "after",
            "limit": 64,
        },
    ]
    redact_values = [
        {
            "headers": {"authorization": "Bearer supersecrettoken1234"},
            "items": [
                1,
                "ghp_0123456789abcdefghijklmnop",
                {"nested": {"key": "AKIAIOSFODNN7EXAMPLE"}},
            ],
        },
        ["ordinary diagnostic", {"api_key": "AbC123dEf456"}],
        {"path": "/tmp/agentrouter/logs/run.txt", "clean": True},
    ]
    route_record = {
        "task": "λx private task text",
        "payload": {
            "classification": {
                "task_type": "coding",
                "risk": "low",
                "confidence": 0.9,
            },
            "recommendation": {
                "model": "openai/gpt-x",
                "provider": "openai",
                "pricing_tier": "mid",
                "score": 1.23,
            },
            "gates": {"auto_execute_allowed": True},
            "excluded": [{"model": "a"}, {"model": "b"}],
            "prompt": "must stay private",
        },
        "decision_id": "d_1",
        "request_id": "req-1",
    }
    strict_values = [
        {"APİ_KEY": "abc", "password": "short", "api_key": "set (value withheld)"},
        {"path": "ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklm/nopqrstuvwxyz.py"},
        [[[[[[{"token": "abc"}, None, 3, True]]]]]],
    ]
    payload = {
        "redact_strict": secrets,
        "redact_value_strict": strict_values,
        "redact": secrets,
        "echo": echo_inputs,
        "redact_value": redact_values,
        "route_record": route_record,
    }
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-cli", "--bin", "observability_cli"],
        cwd=root,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    rust = json.loads(result.stdout)
    assert rust["redact_strict"] == [observability.redact_strict(value) for value in secrets]
    assert rust["redact_value_strict"] == [
        observability.redact_value(value, _preserve_paths=False) for value in strict_values
    ]
    assert rust["redact"] == [observability.redact(secret) for secret in secrets]
    for secret in (
        "postgres://user:allletters@db.internal/x",
        "provider/ABCDEFGHIJKLMNOPQRSTUVWXabcdefghijklm",
    ):
        assert secret not in rust["redact"][secrets.index(secret)]
    assert rust["echo"] == [
        observability.safe_echo(item["text"], item["limit"]) for item in echo_inputs
    ]
    assert rust["redact_value"] == [observability.redact_value(value) for value in redact_values]
    assert rust["route_record"] == observability.route_decision_record(
        task=route_record["task"],
        payload=route_record["payload"],
        decision_id=route_record["decision_id"],
        request_id=route_record["request_id"],
    )
    record_json = json.dumps(rust["route_record"])
    assert "private task text" not in record_json
    assert "must stay private" not in record_json
