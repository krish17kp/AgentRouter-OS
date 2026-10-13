"""TASK-001 — structured route logging + opt-in OpenTelemetry (backlog L1)."""

from __future__ import annotations

import json
import logging

import pytest

pytest.importorskip("fastapi")  # optional [server] extra

from fastapi.testclient import TestClient  # noqa: E402

from agentrouter import observability as obs  # noqa: E402
from agentrouter.server.app import create_app  # noqa: E402

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
def client(home):
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


# --- widened redaction (second review round) ---------------------------------
#
# The first version matched four vendor prefixes. A reviewer passed 16 of 23 real
# credential formats straight through it. Redaction is the ONLY control between a
# malformed registry and the log, so the list is now generic (keyword adjacency +
# long high-entropy runs) rather than a catalogue of prefixes.


@pytest.mark.parametrize(
    "secret",
    [
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
    ],
)
def test_redact_masks_real_credential_formats(secret):
    masked = obs.redact(f"failed while using {secret} here")
    # the distinctive part of the credential must not survive
    assert secret.split()[-1][:14] not in masked
    assert "[redacted]" in masked
    assert "failed while using" in masked  # the diagnosable part survives


def test_redact_leaves_ordinary_diagnostics_intact():
    for text in (
        "Registry file not found: providers.yaml (run: agentrouter init)",
        "no decision 'd_00001'",
        "context_band_accuracy 0.6667 below 0.90",
    ):
        assert obs.redact(text) == text


def test_redaction_recurses_into_nested_values():
    """`log_event` used to redact only values that were already strings."""
    record = obs.redact_value(
        {
            "headers": {"authorization": "Bearer supersecrettoken1234"},
            "items": [1, "ghp_0123456789abcdefghijklmnop", {"k": "AKIAIOSFODNN7EXAMPLE"}],
        }
    )
    flat = json.dumps(record)
    assert "supersecret" not in flat
    assert "ghp_0123" not in flat
    assert "AKIAIOSF" not in flat


def test_log_event_redacts_non_string_values(caplog):
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    obs.log_event("catalog.failed", detail={"authorization": "Bearer supersecrettoken1234"})
    assert "supersecret" not in caplog.text
    assert "[redacted]" in caplog.text


def test_quiet_api_error_omits_message_and_traceback(caplog):
    """`detail=False` is for the user's data being wrong, not a bug: the text
    quotes the offending file, and the endpoint may be unauthenticated."""
    caplog.set_level(logging.INFO, logger="agentrouter.route")
    try:
        raise ValueError("Invalid YAML in /home/u/registry/models.yaml: token: AIzaSyABCDEFG")
    except ValueError as exc:
        record = obs.log_api_error("api.registry_error", exc, detail=False, remedy="run doctor")

    assert record["error_type"] == "ValueError"
    assert "message" not in record
    assert record["remedy"] == "run doctor"
    text = caplog.text
    assert "Traceback" not in text
    assert "/home/u/registry" not in text
    assert "AIzaSy" not in text
    assert "run doctor" in text  # still actionable


# --- redaction must stay secure AND usable (TASK-018C) ------------------------
#
# The widened catch-all did its job too well: a 44-character run like
# `Projects/Agentrouteros/agentrouter/server/app` matched, so file paths vanished
# from tracebacks — exactly where a path is the most useful thing on the line.
# The narrowing must not unmask anything that was masked before, so both
# directions are asserted together.


@pytest.mark.parametrize(
    "path",
    [
        "/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros/agentrouter/server/app.py",
        "agentrouter/evaluation/evaluators/context_bands.py",
        "/usr/lib/python3/dist-packages/something/deeply/nested/module/handler.py",
        "New Volume/Krish/Dev Projects/Agentrouteros/agentrouter/reliability/harness.py",
    ],
)
def test_file_paths_survive_redaction(path):
    """A redacted traceback is a traceback nobody can act on."""
    assert "[redacted]" not in obs.redact(path), path


@pytest.mark.parametrize(
    "secret",
    [
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
        # An AWS secret access key contains slashes AND digits — the case the
        # path discriminator must NOT let through.
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY1",
        "Bearer eyJhbGciOiJIUzI1NiJ9.abcdefgh.signature",
        "Basic dXNlcjpwYXNzd29yZA==",
        "postgres://user:hunter2@db.internal:5432/x",
        'password="hunter2secret"',
        "api_key: AbC123dEf456",
    ],
)
def test_narrowing_the_catch_all_unmasked_nothing(secret):
    """Every format masked before the narrowing is still masked after it."""
    masked = obs.redact(f"failed while using {secret} here")
    assert "[redacted]" in masked, secret
    assert secret.split()[-1][:14] not in masked, secret


def test_a_traceback_keeps_its_paths_but_loses_its_secrets():
    """The end-to-end property: diagnosable and safe at the same time."""
    trace = (
        'File "/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros'
        '/agentrouter/server/service.py", line 127, in route_task\n'
        "    raise RuntimeError('bad key AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P')\n"
    )
    masked = obs.redact(trace)
    assert "service.py" in masked and "route_task" in masked
    assert "AIzaSy" not in masked and "[redacted]" in masked
