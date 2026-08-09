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


# ---- redaction (TASK-018A) ----
#
# log_event/log_api_error exist to make a typed 500 diagnosable. They carry text
# nobody enumerated in advance, which is exactly where a stray credential shows
# up — so redaction is a property of the sink, not of each call site.


@pytest.mark.parametrize(
    "secret",
    [
        "sk-livekey0123456789abcdef",
        "ghp_0123456789abcdefghijklmnop",
        "Bearer eyJhbGciOiJIUzI1NiJ9.abc",
        "AKIAIOSFODNN7EXAMPLE",
    ],
)
def test_redact_masks_credential_shapes(secret):
    masked = obs.redact(f"failed while using {secret} here")
    assert secret not in masked
    assert "[redacted]" in masked
    assert "failed while using" in masked  # the diagnosable part survives


def test_redact_leaves_ordinary_text_alone():
    text = "Registry file not found: providers.yaml (run: agentrouter init)"
    assert obs.redact(text) == text


def test_log_event_redacts_string_values(caplog):
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    obs.set_request_id("req-redact")
    try:
        record = obs.log_event("catalog.refresh_failed", detail="key sk-livekey0123456789abcdef")
    finally:
        obs.set_request_id(None)
    assert "[redacted]" in record["detail"]
    assert "sk-livekey" not in caplog.text
    assert record["request_id"] == "req-redact"


def test_log_api_error_records_the_traceback_at_error_level(caplog):
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    try:
        raise ValueError("boom with sk-livekey0123456789abcdef")
    except ValueError as exc:
        record = obs.log_api_error("api.unhandled_error", exc)

    assert record["error_type"] == "ValueError"
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert errors, "an unhandled API error must be logged at ERROR, not INFO"
    text = "\n".join(r.getMessage() for r in errors)
    assert "Traceback (most recent call last)" in text  # diagnosable
    assert "sk-livekey" not in text and "[redacted]" in text


def test_log_api_error_does_not_pass_exc_info(caplog):
    """exc_info would let logging render the *raw* exception message, which is
    precisely the string redaction is protecting."""
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    try:
        raise ValueError("sk-livekey0123456789abcdef")
    except ValueError as exc:
        obs.log_api_error("api.unhandled_error", exc)
    assert all(r.exc_info is None for r in caplog.records)
    assert "sk-livekey" not in caplog.text
