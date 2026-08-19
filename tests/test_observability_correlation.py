"""Correlation-ID tracing across every layer (TASK-018C).

A request id is only worth having if it survives the whole path. When a user
reports "request abc-123 failed", an operator must be able to find that id in
the log line for the routing decision — not just in the HTTP response header.

The chain under test: SDK/client -> API -> middleware -> service -> log record
-> response header.
"""

from __future__ import annotations

import json
import logging

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from agentrouter import observability as obs  # noqa: E402
from agentrouter.cli import app as cli_app  # noqa: E402
from agentrouter.server.app import create_app  # noqa: E402

runner = CliRunner()
TRACE = "trace-me-0001"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    return TestClient(create_app(), raise_server_exceptions=False)


def _records(caplog) -> list[dict]:
    out = []
    for record in caplog.records:
        if record.name != "agentrouter.route":
            continue
        try:
            out.append(json.loads(record.getMessage().splitlines()[0]))
        except (ValueError, IndexError):
            continue
    return out


def test_a_client_supplied_id_reaches_the_log_and_comes_back(client, caplog):
    """The whole point: correlate what the user saw with what the server logged."""
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    response = client.post(
        "/v1/route", json={"task": "refactor the parser"}, headers={"X-Request-ID": TRACE}
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == TRACE

    logged = _records(caplog)
    assert logged, "no structured record was emitted for the route"
    assert any(r.get("request_id") == TRACE for r in logged), logged


def test_a_generated_id_is_also_correlatable(client, caplog):
    """A client that sends no id must still be traceable."""
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    response = client.post("/v1/route", json={"task": "write docs"})
    generated = response.headers["X-Request-ID"]
    assert generated

    logged = _records(caplog)
    assert any(r.get("request_id") == generated for r in logged), (generated, logged)


def test_a_failure_is_correlatable_too(client, caplog, monkeypatch):
    """The case that matters most: the id must survive the error path."""
    from agentrouter.server import service

    monkeypatch.setattr(
        service, "route_task", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    caplog.set_level(logging.ERROR, logger="agentrouter.route")
    response = client.post("/v1/route", json={"task": "x"}, headers={"X-Request-ID": TRACE})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == TRACE
    assert any(r.get("request_id") == TRACE for r in _records(caplog))


def test_the_id_does_not_leak_between_sequential_requests(client, caplog):
    """A stale contextvar would attribute one caller's log line to another."""
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    client.post("/v1/route", json={"task": "first"}, headers={"X-Request-ID": "id-one"})
    client.post("/v1/route", json={"task": "second"}, headers={"X-Request-ID": "id-two"})

    ids = [r.get("request_id") for r in _records(caplog) if r.get("event") == "route_decision"]
    assert "id-one" in ids and "id-two" in ids
    assert ids.count("id-one") == 1, ids
    assert ids.count("id-two") == 1, ids


def test_the_request_id_is_cleared_after_the_request(client):
    """Otherwise a later CLI call in the same process inherits a stale id."""
    client.post("/v1/route", json={"task": "x"}, headers={"X-Request-ID": TRACE})
    assert obs.get_request_id() is None


# --- metrics cardinality ------------------------------------------------------


def test_the_decision_record_carries_no_high_cardinality_label(client, caplog):
    """Request ids, prompts, task text and user names must never become metric
    labels — each one turns a counter into an unbounded series."""
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    client.post("/v1/route", json={"task": "a very distinctive task string"})

    for record in _records(caplog):
        if record.get("event") != "route_decision":
            continue
        # request_id is present for CORRELATION and is explicitly not a metric
        # dimension; everything else must be bounded-cardinality metadata.
        dimensions = set(record) - {"request_id", "decision_id", "event"}
        assert "task" not in dimensions
        assert "prompt" not in dimensions
        assert "user" not in dimensions
        assert "a very distinctive task string" not in json.dumps(record)
        # task_len is a number, not the text
        assert isinstance(record.get("task_len", 0), int)


def test_route_span_attributes_are_metadata_only(monkeypatch):
    """OTel span attributes go to a tracing backend; raw text must not."""
    monkeypatch.delenv("AGENTROUTER_OTEL", raising=False)
    with obs.route_span("route", task_type="coding", risk="low") as span:
        assert span is None  # no-op unless explicitly opted in
