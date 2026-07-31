"""TASK-001 — structured route logging + opt-in OpenTelemetry (backlog L1)."""

from __future__ import annotations

import json
import logging

import pytest

pytest.importorskip("fastapi")  # optional [server] extra

from fastapi.testclient import TestClient  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from agentrouter import observability as obs  # noqa: E402
from agentrouter.cli import app as cli_app  # noqa: E402
from agentrouter.server.app import create_app  # noqa: E402

runner = CliRunner()

SAMPLE_PAYLOAD = {
    "classification": {"task_type": "coding", "risk": "low", "confidence": 0.9},
    "recommendation": {
        "model": "openai/gpt-x",
        "provider": "openai",
        "pricing_tier": "mid",
        "score": 1.23,
    },
    "gates": {"auto_execute_allowed": True},
    "excluded": [{"model": "a"}, {"model": "b"}],
}


@pytest.fixture(autouse=True)
def _reset_request_id():
    obs.set_request_id(None)
    yield
    obs.set_request_id(None)


# ---- record content + privacy ----


def test_record_has_expected_fields():
    rec = obs.route_decision_record(
        task="refactor the auth module",
        payload=SAMPLE_PAYLOAD,
        decision_id="d_1",
        request_id="rid-1",
    )
    assert rec["event"] == "route_decision"
    assert rec["request_id"] == "rid-1"
    assert rec["decision_id"] == "d_1"
    assert rec["task_type"] == "coding"
    assert rec["risk"] == "low"
    assert rec["recommended_model"] == "openai/gpt-x"
    assert rec["excluded_count"] == 2
    assert rec["task_len"] == len("refactor the auth module")


def test_record_never_contains_raw_task_or_prompt():
    secret_task = "SUPERSECRET internal deploy token abc123"
    payload = {**SAMPLE_PAYLOAD, "prompt": "PROMPT-" + secret_task}
    rec = obs.route_decision_record(task=secret_task, payload=payload)
    blob = json.dumps(rec)
    assert secret_task not in blob
    assert "PROMPT-" not in blob
    assert "prompt" not in rec


def test_record_survives_missing_recommendation():
    payload = {
        "classification": {"task_type": "qa", "risk": "high"},
        "recommendation": None,
        "gates": {},
    }
    rec = obs.route_decision_record(task="x", payload=payload, decision_id=None)
    assert rec["task_type"] == "qa"
    assert "recommended_model" not in rec  # None dropped
    assert "decision_id" not in rec  # None dropped


# ---- emission + request-id propagation ----


def test_log_route_decision_emits_json(caplog):
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    obs.log_route_decision(task="hello", payload=SAMPLE_PAYLOAD, decision_id="d_9")
    msgs = [r.message for r in caplog.records if r.name == "agentrouter.route"]
    assert len(msgs) == 1
    parsed = json.loads(msgs[0])
    assert parsed["decision_id"] == "d_9"


def test_request_id_contextvar_used_when_not_passed():
    obs.set_request_id("ctx-rid")
    rec = obs.route_decision_record(task="x", payload=SAMPLE_PAYLOAD)
    assert rec["request_id"] == "ctx-rid"


# ---- OTel opt-in / no-op ----


def test_route_span_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("AGENTROUTER_OTEL", raising=False)
    with obs.route_span("route", task_type="coding") as span:
        assert span is None


def test_route_span_noop_when_otel_missing(monkeypatch):
    # Opted in, but opentelemetry is not installed in the test env -> still no-op.
    monkeypatch.setenv("AGENTROUTER_OTEL", "1")
    if obs.otel_enabled():
        pytest.skip("opentelemetry is installed; no-op-when-missing path not exercised")
    with obs.route_span("route") as span:
        assert span is None


def test_configure_logging_opt_in(monkeypatch):
    monkeypatch.delenv("AGENTROUTER_LOG", raising=False)
    assert obs.configure_logging() is False
    monkeypatch.setenv("AGENTROUTER_LOG", "1")
    assert obs.configure_logging() is True
    # idempotent: no duplicate agentrouter handlers
    obs.configure_logging()
    ours = [h for h in obs.logger.handlers if getattr(h, "_agentrouter", False)]
    assert len(ours) == 1


# ---- server integration: log carries the X-Request-ID ----


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    return TestClient(create_app())


def test_server_route_logs_with_request_id(client, caplog):
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    r = client.post(
        "/v1/route", json={"task": "summarize a PR"}, headers={"X-Request-ID": "req-777"}
    )
    assert r.status_code == 200
    records = [json.loads(rec.message) for rec in caplog.records if rec.name == "agentrouter.route"]
    assert records, "expected a route_decision log record"
    assert records[-1]["request_id"] == "req-777"
    assert "summarize a PR" not in caplog.text  # no raw task text in logs
