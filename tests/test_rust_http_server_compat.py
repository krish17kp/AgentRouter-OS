"""End-to-end checks against the Rust HTTP server process."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


@contextmanager
def _server(home: Path, settings: dict[str, str] | None = None):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {
        **os.environ,
        "AGENTROUTER_HOME": str(home),
        "CARGO_BUILD_JOBS": "1",
        "CARGO_PROFILE_DEV_DEBUG": "0",
        "CARGO_INCREMENTAL": "0",
    }
    environment.pop("AGENTROUTER_API_KEY", None)
    environment.pop("AGENTROUTER_CORS_ORIGINS", None)
    if settings:
        environment.update(settings)
    process = subprocess.Popen(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-api",
            "--bin",
            "agentrouter-api-server",
            "--",
            "--bind",
            f"127.0.0.1:{port}",
            "--home",
            str(home),
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f"Rust API server exited during startup ({process.returncode})")
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=0.25):
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            pytest.fail("Rust API server did not become ready within 45 seconds")
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _request(base: str, path: str, method: str = "GET", body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        response = urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    return response.status, response.headers, json.loads(raw) if raw else None


def _request_raw(base: str, path: str, raw: bytes, headers=None):
    request = urllib.request.Request(
        base + path,
        data=raw,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    payload = response.read()
    return response.status, json.loads(payload) if payload else None


def test_rust_http_server_matches_public_local_api(home):
    with _server(home) as base:
        status, headers, payload = _request(base, "/health")
        assert status == 200 and payload == {"status": "ok"}
        assert headers.get("X-Request-ID")

        assert _request(base, "/ready")[2] == {"status": "ready"}
        status, _, models = _request(base, "/v1/models")
        assert status == 200 and models and models[0]["model_id"]
        status, _, hosts = _request(base, "/v1/hosts")
        assert status == 200 and any(row["host"] == "manual" for row in hosts)

        status, _, classification = _request(
            base,
            "/v1/classify",
            "POST",
            {"task": "review this repository for security issues", "risk": "high"},
        )
        assert status == 200 and classification["risk"] == "high"

        status, _, preview = _request(
            base,
            "/v1/route",
            "POST",
            {"task": "summarize a report", "no_log": True},
        )
        assert status == 200 and preview["decision_id"] is None

        status, _, route = _request(
            base, "/v1/route", "POST", {"task": "write a short project guide"}
        )
        assert status == 200 and route["decision_id"]
        decision_id = route["decision_id"]
        status, _, decision = _request(base, f"/v1/decisions/{decision_id}")
        assert status == 200 and decision["decision_id"] == decision_id

        status, _, feedback = _request(
            base,
            "/v1/feedback",
            "POST",
            {"decision_id": decision_id, "rating": 5, "note": None},
        )
        assert status == 200 and feedback == {"decision_id": decision_id, "recorded": True}

        status, _, dry_run = _request(
            base, "/v1/execute/dry-run", "POST", {"decision_id": decision_id}
        )
        assert status == 200 and dry_run["would_execute"] is False

        status, _, missing = _request(base, "/v1/decisions/d_99999")
        assert status == 404 and missing["error"]["code"] == "not_found"
        status, _, invalid = _request(base, "/v1/classify", "POST", {})
        assert status == 422 and invalid["error"]["code"] == "validation_error"
        status, _, unknown = _request(base, "/v1/removed")
        assert status == 404 and unknown["error"]["code"] == "not_found"

        status, _, contract = _request(base, "/openapi.json")
        expected = json.loads((ROOT / "contracts/http/v1/openapi.json").read_text())
        assert status == 200 and contract == expected


def test_rust_http_server_matches_python_service_responses(home, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from agentrouter.server.app import create_app

    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENTROUTER_CORS_ORIGINS", raising=False)
    cases = [
        ("GET", "/v1/models", None),
        ("GET", "/v1/hosts", None),
        (
            "POST",
            "/v1/classify",
            {"task": "review this Python repository for security issues", "risk": "high"},
        ),
        (
            "POST",
            "/v1/route",
            {"task": "summarize a report", "no_log": True},
        ),
    ]
    with TestClient(create_app()) as python_api, _server(home) as rust_api:
        for method, path, body in cases:
            python_response = python_api.request(method, path, json=body)
            rust_status, _, rust_payload = _request(rust_api, path, method, body)
            assert rust_status == python_response.status_code, path
            assert rust_payload == python_response.json(), path


def test_rust_http_server_matches_python_validation_errors(home, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from agentrouter.server.app import create_app

    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENTROUTER_CORS_ORIGINS", raising=False)
    too_many_tools = ["tool"] * 101
    too_long_task = "x" * 100_001
    too_long_note = "x" * 10_001
    cases = [
        ("/v1/classify", {}),
        ("/v1/classify", {"task": ""}),
        ("/v1/classify", {"task": 7}),
        ("/v1/classify", {"task": too_long_task}),
        ("/v1/classify", {"task": "x", "context_tokens": 1.5}),
        ("/v1/classify", {"task": "x", "context_tokens": 0}),
        ("/v1/classify", {"task": "x", "risk": "critical"}),
        ("/v1/classify", {"task": "x", "tools": "search"}),
        ("/v1/classify", {"task": "x", "tools": ["search", 7]}),
        ("/v1/classify", {"task": "x", "tools": too_many_tools}),
        ("/v1/route", {"task": "x", "prefer": 7}),
        ("/v1/route", {"task": "x", "no_log": "maybe"}),
        ("/v1/feedback", {}),
        ("/v1/feedback", {"decision_id": "d", "rating": 0}),
        ("/v1/feedback", {"decision_id": "d", "rating": 1.5}),
        ("/v1/feedback", {"decision_id": "d", "rating": 6}),
        ("/v1/feedback", {"decision_id": "d", "rating": 5, "note": 7}),
        (
            "/v1/feedback",
            {"decision_id": "d", "rating": 5, "note": too_long_note},
        ),
        ("/v1/feedback", {"decision_id": "", "rating": 5}),
        ("/v1/execute/dry-run", {}),
        ("/v1/execute/dry-run", []),
    ]
    with TestClient(create_app()) as python_api, _server(home) as rust_api:
        for path, body in cases:
            python_response = python_api.post(path, json=body)
            rust_status, _, rust_payload = _request(rust_api, path, "POST", body)
            assert rust_status == python_response.status_code == 422, path
            assert rust_payload == python_response.json(), (path, body)

        python_invalid_json = python_api.post(
            "/v1/classify",
            content=b"{bad",
            headers={"content-type": "application/json"},
        )
        rust_status, rust_payload = _request_raw(rust_api, "/v1/classify", b"{bad")
        assert rust_status == python_invalid_json.status_code == 422
        assert rust_payload == python_invalid_json.json()

        python_missing_route = python_api.get("/v1/removed")
        rust_status, _, rust_payload = _request(rust_api, "/v1/removed")
        assert rust_status == python_missing_route.status_code == 404
        assert rust_payload == python_missing_route.json()


def test_rust_http_server_authentication_and_cors_allowlist(home):
    settings = {
        "AGENTROUTER_API_KEY": "test-secret",
        "AGENTROUTER_CORS_ORIGINS": "https://console.example",
    }
    with _server(home, settings) as base:
        status, _, unauthorized = _request(base, "/v1/models")
        assert status == 401 and unauthorized["error"]["code"] == "unauthorized"
        status, _, models = _request(base, "/v1/models", headers={"X-API-Key": "test-secret"})
        assert status == 200 and models
        assert _request(base, "/health")[0] == 200

        request = urllib.request.Request(
            base + "/v1/route",
            headers={
                "Origin": "https://console.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
            method="OPTIONS",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
            assert response.headers["Access-Control-Allow-Origin"] == "https://console.example"
            assert response.headers.get("X-Request-ID")


def test_rust_http_server_rate_limit_and_idempotency_are_bounded(home):
    with _server(
        home,
        {"AGENTROUTER_RATE_LIMIT": "6", "AGENTROUTER_RATE_WINDOW": "60"},
    ) as base:
        body = {"task": "write a guide to the router"}

        def route_once(_index):
            return _request(
                base,
                "/v1/route",
                "POST",
                body,
                {"Idempotency-Key": "same-operation"},
            )

        with ThreadPoolExecutor(max_workers=5) as executor:
            responses = list(executor.map(route_once, range(5)))
        assert all(status == 200 for status, _, _ in responses)
        decision_ids = {payload["decision_id"] for _, _, payload in responses}
        assert len(decision_ids) == 1
        replay_headers = [headers.get("Idempotency-Replay") for _, headers, _ in responses]
        assert sorted(replay_headers) == ["false", "true", "true", "true", "true"]

        changed_body = {"task": "summarize a report"}
        status, _, changed_route = _request(
            base,
            "/v1/route",
            "POST",
            changed_body,
            {"Idempotency-Key": "same-operation"},
        )
        assert status == 200 and changed_route["decision_id"] not in decision_ids

        status, headers, limited = _request(base, "/v1/models")
        assert status == 429 and limited["error"]["code"] == "rate_limited"
        assert headers.get("Retry-After") and headers.get("X-Request-ID")
        assert _request(base, "/health")[0] == 200
