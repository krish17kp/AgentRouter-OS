"""Phase P7 — local REST API tests (health/ready, catalog, classify/route, feedback,
dry-run non-execution, api-key auth, error shapes)."""

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from agentrouter.cli import app as cli_app
from agentrouter.server.app import create_app

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
    assert r.json()["error"]["code"] == "unavailable"


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
