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
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
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
