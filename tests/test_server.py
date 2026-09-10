"""Phase P7 — local REST API tests (health/ready, catalog, classify/route, feedback,
dry-run non-execution, api-key auth, error shapes)."""

import pytest

pytest.importorskip("fastapi")  # optional [server] extra

from fastapi.testclient import TestClient  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from agentrouter.cli import app as cli_app  # noqa: E402
from agentrouter.server.app import create_app  # noqa: E402

runner = CliRunner()


@pytest.fixture()
def client(home):
    return TestClient(create_app())


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers.get("X-Request-ID")  # generated when not supplied


def test_request_id_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


def test_ready_ok(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_ready_503_without_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path / "empty"))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    r = TestClient(create_app()).get("/ready")
    assert r.status_code == 503
    # Readiness and the /v1 routes must report the same code for the same
    # condition — /ready used to answer a vaguer "unavailable".
    assert r.json()["error"]["code"] == "registry_unavailable"
    # The registry path is local filesystem detail; it belongs in the log, not
    # in a response any unauthenticated caller can read.
    assert str(tmp_path) not in r.text


def test_models(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    rows = r.json()
    assert (
        rows
        and {"vendor", "model_id", "release_channel", "context_window", "host_availability"}
        <= rows[0].keys()
    )


def test_hosts(client):
    r = client.get("/v1/hosts")
    assert r.status_code == 200
    hosts = r.json()
    assert any(h["host"] == "manual" and h["availability"] == "available" for h in hosts)


def test_hosts_expose_state_and_remedy(client):
    """TASK-016: additive readiness detail; `availability` keeps its meaning."""
    from agentrouter import hosts as hosts_mod

    payload = client.get("/v1/hosts").json()
    valid_states = {
        hosts_mod.MISSING,
        hosts_mod.INSTALLED,
        hosts_mod.CONFIGURED,
        hosts_mod.AUTHENTICATED,
        hosts_mod.AUTHORIZED,
        hosts_mod.DEGRADED,
        hosts_mod.STATE_UNKNOWN,
    }
    for h in payload:
        assert h["state"] in valid_states
        assert "remedy" in h  # may be null when nothing needs fixing
        # the coarse signal stays derivable from the finer one
        assert h["availability"] == hosts_mod._availability_for(h["state"])
    # an offline API response must never claim a verified authorization
    assert all(h["state"] != hosts_mod.AUTHORIZED for h in payload)


def test_classify(client):
    r = client.post("/v1/classify", json={"task": "write a haiku about routers"})
    assert r.status_code == 200
    body = r.json()
    assert "task_type" in body and "risk" in body


def test_route_persists_and_get_decision(client):
    r = client.post("/v1/route", json={"task": "refactor the auth module for clarity"})
    assert r.status_code == 200
    payload = r.json()
    did = payload["decision_id"]
    assert did and payload["classification"]["task_type"]
    # execution_route present for an eligible recommendation
    assert "execution_route" in payload

    got = client.get(f"/v1/decisions/{did}")
    assert got.status_code == 200
    assert got.json()["decision_id"] == did


def test_route_no_log(client):
    r = client.post("/v1/route", json={"task": "summarize this text", "no_log": True})
    assert r.status_code == 200
    assert r.json()["decision_id"] is None


def test_decision_404(client):
    r = client.get("/v1/decisions/d_99999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_feedback(client):
    did = client.post("/v1/route", json={"task": "write docs"}).json()["decision_id"]
    r = client.post("/v1/feedback", json={"decision_id": did, "rating": 5, "note": "great"})
    assert r.status_code == 200
    assert r.json() == {"decision_id": did, "recorded": True}


def test_feedback_unknown_decision_404(client):
    r = client.post("/v1/feedback", json={"decision_id": "d_00000", "rating": 3})
    assert r.status_code == 404


def test_dry_run_returns_plan_and_does_not_execute(client):
    did = client.post("/v1/route", json={"task": "add a unit test for the parser"}).json()[
        "decision_id"
    ]
    r = client.post("/v1/execute/dry-run", json={"decision_id": did})
    assert r.status_code == 200
    plan = r.json()
    assert plan["would_execute"] is False
    assert plan["decision_id"] == did
    # argv (when present) keeps {prompt} unsubstituted — nothing was run
    if plan["argv"]:
        assert any("{prompt}" in a for a in plan["argv"]) or plan["argv"]


def test_validation_error_shape(client):
    r = client.post("/v1/classify", json={})  # missing required 'task'
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_feedback_rating_bounds(client):
    did = client.post("/v1/route", json={"task": "write docs"}).json()["decision_id"]
    r = client.post("/v1/feedback", json={"decision_id": did, "rating": 9})
    assert r.status_code == 422


# --- api-key auth ---------------------------------------------------------
@pytest.fixture()
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.setenv("AGENTROUTER_API_KEY", "s3cret")
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    return TestClient(create_app())


def test_auth_required_when_key_set(auth_client):
    r = auth_client.get("/v1/models")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_auth_wrong_key(auth_client):
    r = auth_client.get("/v1/models", headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_auth_correct_key(auth_client):
    r = auth_client.get("/v1/models", headers={"X-API-Key": "s3cret"})
    assert r.status_code == 200


def test_health_open_even_with_key(auth_client):
    # health/ready are unauthenticated liveness probes
    assert auth_client.get("/health").status_code == 200


# --- unexpected failures: typed to the client, diagnosable to the operator ----
#
# TASK-018A review: an unhandled exception was answered by Starlette's outermost
# ServerErrorMiddleware — above the request-id middleware — so the client got a
# response with no X-Request-ID, and the @app.exception_handler(Exception) that
# was supposed to shape it never ran at all.


def test_unhandled_error_returns_a_typed_envelope_with_a_request_id(client, monkeypatch):
    from agentrouter.server import service

    def boom(*_a, **_k):
        raise RuntimeError("token sk-livekey0123456789abcdef at /home/someone/secret.yaml")

    monkeypatch.setattr(service, "classify_task", boom)
    r = TestClient(client.app, raise_server_exceptions=False).post(
        "/v1/classify", json={"task": "x"}, headers={"X-Request-ID": "trace-me"}
    )
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "internal server error"}}
    assert r.headers["X-Request-ID"] == "trace-me"  # correlatable
    # No raw traceback may reach the API client.
    for leak in ("Traceback", "RuntimeError", "sk-live", "/home/someone"):
        assert leak not in r.text


def test_unhandled_error_is_logged_with_a_redacted_traceback(client, monkeypatch, caplog):
    from agentrouter.server import service

    def boom(*_a, **_k):
        raise RuntimeError("token sk-livekey0123456789abcdef")

    monkeypatch.setattr(service, "classify_task", boom)
    with caplog.at_level("ERROR", logger="agentrouter.route"):
        TestClient(client.app, raise_server_exceptions=False).post(
            "/v1/classify", json={"task": "x"}
        )
    text = "\n".join(r.getMessage() for r in caplog.records)
    # Catching the error here also stops uvicorn logging it, so an ERROR record
    # is the only thing standing between a 500 and a silent fault.
    assert "api.unhandled_error" in text
    assert "Traceback (most recent call last)" in text
    assert "sk-livekey" not in text and "[redacted]" in text


def test_registry_error_does_not_echo_the_file_or_its_contents(tmp_path, monkeypatch):
    """A registry only fails this way when malformed — exactly when a pasted
    credential is sitting in it. The message is for the log, not the caller."""
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    bad = tmp_path / "registry" / "providers.yaml"
    bad.write_text("api_key: sk-livekey0123456789abcdef\n  bad: [indent\n", encoding="utf-8")

    c = TestClient(create_app())
    for path in ("/ready", "/v1/models"):
        r = c.get(path)
        assert r.status_code == 503, path
        assert r.json()["error"]["code"] == "registry_unavailable", path
        for leak in ("sk-livekey", "providers.yaml", str(tmp_path), "indent"):
            assert leak not in r.text, f"{path} leaked {leak}"


def test_response_models_do_not_strip_engine_owned_fields(client):
    """The typed envelopes exist to make the contract meaningful — if they also
    truncated the payload they would be a silent breaking change of their own."""
    routed = client.post("/v1/route", json={"task": "refactor the parser"})
    assert routed.status_code == 200
    body = routed.json()
    # `scores` and `weights` are engine-owned and not worth re-modelling, but
    # they must still reach the client.
    for key in ("classification", "recommendation", "scores", "weights", "gates"):
        assert key in body, key

    did = body["decision_id"]
    stored = client.get(f"/v1/decisions/{did}").json()
    assert stored["created_at"]  # DecisionResponse adds fields, drops none
    assert set(body) <= set(stored)


# --- second review round: amplification, echo bounds --------------------------


def test_registry_failure_does_not_amplify_into_the_log(tmp_path, monkeypatch, caplog):
    """`/ready` is unauthenticated AND rate-limit exempt.

    Logging the registry exception meant any caller could write ~8 KB of registry
    content — path, offending source line, pasted credential — into the
    operator's log on every request. ERROR records reach stderr even with no
    handler installed, so this needed no opt-in to be exploitable.
    """
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AGENTROUTER_LOG", raising=False)
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    (tmp_path / "registry" / "models.yaml").write_text(
        'models:\n  - key: x\n    token: "AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q\n',
        encoding="utf-8",
    )

    client = TestClient(create_app())
    with caplog.at_level("ERROR", logger="agentrouter.route"):
        for _ in range(20):
            r = client.get("/ready")
    assert r.status_code == 503

    logged = "\n".join(rec.getMessage() for rec in caplog.records)
    per_request = len(logged) / 20
    assert per_request < 600, f"{per_request:.0f} bytes/request is an amplifier"
    assert "Traceback" not in logged
    assert str(tmp_path) not in logged  # no registry path
    assert "AIzaSy" not in logged and "token" not in logged  # no registry content
    assert "doctor" in logged  # still actionable for the operator


def test_unhandled_error_still_logs_its_traceback(client, monkeypatch, caplog):
    """The quiet path is only for user-data errors. A genuine bug must stay loud —
    catching it to return a typed 500 also stops the ASGI server logging it."""
    from agentrouter.server import service

    monkeypatch.setattr(
        service, "classify_task", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaboom"))
    )
    with caplog.at_level("ERROR", logger="agentrouter.route"):
        TestClient(client.app, raise_server_exceptions=False).post(
            "/v1/classify", json={"task": "x"}
        )
    logged = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "api.unhandled_error" in logged
    assert "Traceback (most recent call last)" in logged


def test_echoed_decision_id_is_bounded(client):
    import urllib.parse

    r = client.get("/v1/decisions/" + urllib.parse.quote("A" * 5000))
    assert r.status_code == 404
    assert len(r.text) < 300, "an oversized id must not produce an oversized body"


@pytest.mark.parametrize(
    "hostile",
    [
        "x\n\rFAKE-LOG-LINE: approved",  # log forging
        "x‮detuces-eb-dluow",  # bidi override flips the display
        "x​​hidden",  # zero-width padding
        "x﻿bom",
    ],
)
def test_echoed_decision_id_is_sanitised(client, hostile):
    r = client.post("/v1/feedback", json={"decision_id": hostile, "rating": 3})
    assert r.status_code == 404
    message = r.json()["error"]["message"]
    assert not any(ch in message for ch in "\n\r‮​﻿")


def test_a_real_decision_id_is_echoed_untouched(client):
    r = client.get("/v1/decisions/d_99999")
    assert r.json()["error"]["message"] == "no decision 'd_99999'"
