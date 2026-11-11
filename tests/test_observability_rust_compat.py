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
    payload = {"redact": secrets, "echo": echo_inputs}
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["cargo", "run", "--quiet", "-p", "agentrouter-cli", "--bin", "observability_cli"],
        cwd=root,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    rust = json.loads(result.stdout)
    assert rust["redact"] == [observability.redact(secret) for secret in secrets]
    assert rust["echo"] == [
        observability.safe_echo(item["text"], item["limit"]) for item in echo_inputs
    ]
