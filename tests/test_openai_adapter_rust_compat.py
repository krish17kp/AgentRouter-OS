"""Differential checks for the offline OpenAI Responses adapter contract."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from agentrouter import openai_adapter

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]
FIXTURE_KEY = "fixture-only-key"


@pytest.fixture(scope="session")
def rust_openai_probe():
    built = subprocess.run(
        ["cargo", "build", "--locked", "-p", "agentrouter-cli", "--bin", "openai_from_json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target"))
    binary = target / "debug" / "openai_from_json"
    if os.name == "nt":
        binary = binary.with_suffix(".exe")
    assert binary.exists()
    return binary


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int):
        return self.body[:limit]


def _rust(binary: Path, case: dict) -> dict:
    result = subprocess.run(
        [str(binary)],
        cwd=ROOT,
        input=json.dumps(case),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _python(case: dict, monkeypatch) -> dict:
    body = case.get("response_body", "").encode()
    status = case.get("status", 200)
    transport_error = case.get("transport_error")

    def fake_open(*_args, **_kwargs):
        if transport_error == "network":
            raise URLError("fixture network detail")
        if transport_error == "http_status" or status >= 400:
            raise HTTPError(openai_adapter.RESPONSES_URL, status, "fixture", {}, None)
        return _Response(body)

    monkeypatch.setattr(openai_adapter, "urlopen", fake_open)
    try:
        text = openai_adapter.run_text_response(
            case.get("model_id", "model"),
            case.get("prompt", "prompt"),
            case.get("api_key", FIXTURE_KEY),
            max_output_tokens=case.get("max_output_tokens", 100),
        )
        return {"text": text}
    except openai_adapter.OpenAIAdapterError as error:
        return {"error": str(error)}


def test_success_request_and_text_match_python_without_exposing_key(rust_openai_probe, monkeypatch):
    case = {
        "model_id": "gpt-fixture",
        "prompt": "Write a short answer.",
        "api_key": FIXTURE_KEY,
        "max_output_tokens": 99999,
        "status": 200,
        "response_body": json.dumps(
            {
                "status": "completed",
                "output": [
                    {"type": "reasoning", "summary": []},
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "first"},
                            {"type": "output_text", "text": "second"},
                        ],
                    },
                ],
            }
        ),
    }
    rust = _rust(rust_openai_probe, case)
    assert {key: rust[key] for key in ("text", "error") if key in rust} == _python(
        case, monkeypatch
    )
    assert rust["request"] == {
        "url": openai_adapter.RESPONSES_URL,
        "body": {
            "model": case["model_id"],
            "input": case["prompt"],
            "max_output_tokens": openai_adapter.MAX_OUTPUT_TOKENS,
            "store": False,
            "stream": False,
        },
        "timeout_seconds": openai_adapter.TIMEOUT_SECONDS,
        "max_response_bytes": openai_adapter.MAX_RESPONSE_BYTES,
        "authorization_matches_fixture_key": True,
    }
    assert FIXTURE_KEY not in json.dumps(rust)


@pytest.mark.parametrize(
    "case",
    [
        {"transport_error": "http_status", "status": 429},
        {"transport_error": "network"},
        {"status": 503},
        {"response_body": "not-json"},
        {"response_body": json.dumps([])},
        {"response_body": '{"status":"in_progress","output":[]}'},
        {"response_body": '{"status":"completed"}'},
        {"response_body": '{"status":"completed","output":"not a list"}'},
        {
            "response_body": json.dumps(
                {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "output_text", "text": "not assistant"}],
                        }
                    ],
                }
            )
        },
        {
            "response_body": json.dumps(
                {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": 123}],
                        }
                    ],
                }
            )
        },
        {
            "response_body": json.dumps(
                {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "refusal", "refusal": "no"}],
                        }
                    ],
                }
            )
        },
        {
            "response_body": json.dumps(
                {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "   "}],
                        }
                    ],
                }
            )
        },
        {"model_id": "", "response_body": '{"status":"completed","output":[]}'},
        {"api_key": "", "response_body": '{"status":"completed","output":[]}'},
        {"max_output_tokens": 0, "response_body": '{"status":"completed","output":[]}'},
        {"max_output_tokens": -1, "response_body": '{"status":"completed","output":[]}'},
        {"api_key": "   ", "response_body": '{"status":"completed","output":[]}'},
        {"prompt": "", "response_body": '{"status":"completed","output":[]}'},
        {"response_body": "x" * (openai_adapter.MAX_RESPONSE_BYTES + 1)},
    ],
)
def test_response_and_validation_errors_match_python(rust_openai_probe, monkeypatch, case):
    request = {
        "model_id": "model",
        "prompt": "prompt",
        "api_key": FIXTURE_KEY,
        "max_output_tokens": 100,
        "status": 200,
        "response_body": '{"status":"completed","output":[]}',
        **case,
    }
    rust = _rust(rust_openai_probe, request)
    python = _python(request, monkeypatch)
    assert {key: rust[key] for key in ("text", "error") if key in rust} == python
