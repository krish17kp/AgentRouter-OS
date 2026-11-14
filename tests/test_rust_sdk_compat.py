"""Differential tests for the synchronous Rust and Python API clients."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from agentrouter.sdk import AgentRouterClient, AgentRouterError

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


class _FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        self.requests: list[dict] = []
        super().__init__(("127.0.0.1", 0), _Handler)


class _Handler(BaseHTTPRequestHandler):
    server: _FixtureServer

    def do_GET(self) -> None:
        self._respond()

    def do_POST(self) -> None:
        self._respond()

    def _respond(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw) if raw else None
        self.server.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "body": body,
                "api_key": self.headers.get("X-API-Key"),
            }
        )
        if self.path == "/v1/decisions/missing":
            status, payload = 404, {"error": {"code": "not_found", "message": "decision missing"}}
        else:
            status = 200
            payload = {
                "/health": {"status": "ok"},
                "/ready": {"status": "ready"},
                "/v1/models": [{"model_id": "fixture-model"}],
                "/v1/hosts": [{"host": "manual"}],
                "/v1/classify": {"task_type": "coding", "confidence": 0.82},
                "/v1/route": {
                    "decision_id": "d_fixture",
                    "no_log": body.get("no_log", False) if body else False,
                },
                "/v1/feedback": {"accepted": True},
                "/v1/execute/dry-run": {"executed": False, "dry_run": True},
            }[self.path]
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


@contextmanager
def _serve_fixture() -> Iterator[tuple[str, _FixtureServer]]:
    server = _FixtureServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _operations() -> list[dict]:
    return [
        {"name": "health"},
        {"name": "ready"},
        {"name": "models"},
        {"name": "hosts"},
        {
            "name": "classify",
            "task": "review this repository",
            "context_tokens": 0,
            "risk": "high",
            "tools": ["search", "read"],
        },
        {
            "name": "route",
            "task": "summarize the report",
            "prefer": "fast",
            "context_tokens": 128,
            "risk": "low",
            "tools": ["summarize"],
            "no_log": True,
        },
        {"name": "get_decision", "decision_id": "missing"},
        {"name": "feedback", "decision_id": "d_fixture", "rating": 0, "note": ""},
        {"name": "execute_dry_run", "decision_id": "d_fixture"},
    ]


def _python_results(client: AgentRouterClient) -> list[dict]:
    operations = _operations()
    results = []
    for operation in operations:
        name = operation["name"]
        try:
            if name in {"health", "ready", "models", "hosts"}:
                value = getattr(client, name)()
            elif name == "classify":
                value = client.classify(
                    operation["task"],
                    context_tokens=operation["context_tokens"],
                    risk=operation["risk"],
                    tools=operation["tools"],
                )
            elif name == "route":
                value = client.route(
                    operation["task"],
                    prefer=operation["prefer"],
                    context_tokens=operation["context_tokens"],
                    risk=operation["risk"],
                    tools=operation["tools"],
                    no_log=operation["no_log"],
                )
            elif name == "get_decision":
                value = client.get_decision(operation["decision_id"])
            elif name == "feedback":
                value = client.feedback(
                    operation["decision_id"], operation["rating"], operation["note"]
                )
            else:
                value = client.execute_dry_run(operation["decision_id"])
            results.append({"ok": value})
        except AgentRouterError as error:
            results.append(
                {
                    "error": {
                        "status_code": error.status_code,
                        "code": error.code,
                        "display": str(error),
                    }
                }
            )
    return results


def _rust(request: dict) -> list[dict]:
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "sdk_from_json",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


@pytest.mark.parametrize("api_key", ["fixture-secret", None, ""])
def test_rust_sdk_matches_python_all_endpoints_and_structured_errors(api_key: str | None):
    with _serve_fixture() as (base_url, server):
        base_url = base_url + "/"
        with AgentRouterClient(base_url, api_key=api_key) as client:
            python_results = _python_results(client)
        python_requests = list(server.requests)
        server.requests.clear()

        rust_results = _rust(
            {
                "base_url": base_url,
                "api_key": api_key,
                "timeout_seconds": 10,
                "operations": _operations(),
            }
        )
        rust_requests = list(server.requests)

    assert rust_results == python_results
    assert rust_requests == python_requests
    assert len(rust_requests) == 9
    assert all(request["api_key"] == (api_key or None) for request in rust_requests)
