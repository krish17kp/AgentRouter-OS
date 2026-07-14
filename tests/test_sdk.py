"""Phase P7 — SDK client tests, driven against a real uvicorn server in a thread.

httpx's ASGITransport is async-only and the SDK is sync, so a background uvicorn
process gives a faithful end-to-end HTTP exercise of the client.
"""

import threading
import time

import pytest
import uvicorn
from typer.testing import CliRunner

from agentrouter.cli import app as cli_app
from agentrouter.sdk import AgentRouterClient, AgentRouterError
from agentrouter.server.app import create_app

runner = CliRunner()


def _serve():
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, f"http://127.0.0.1:{port}"


@pytest.fixture()
def sdk(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    server, thread, url = _serve()
    client = AgentRouterClient(url)
    yield client
    client.close()
    server.should_exit = True
    thread.join(timeout=5)


def test_health_and_ready(sdk):
    assert sdk.health() == {"status": "ok"}
    assert sdk.ready()["status"] == "ready"


def test_models_and_hosts(sdk):
    assert sdk.models()
    assert any(h["host"] == "manual" for h in sdk.hosts())


def test_classify(sdk):
    body = sdk.classify("write a haiku", context_tokens=500)
    assert "task_type" in body


def test_route_and_decision_roundtrip(sdk):
    payload = sdk.route("refactor the parser")
    did = payload["decision_id"]
    assert did
    assert sdk.get_decision(did)["decision_id"] == did


def test_feedback(sdk):
    did = sdk.route("write docs")["decision_id"]
    assert sdk.feedback(did, 4, note="ok")["recorded"] is True


def test_dry_run_no_execution(sdk):
    did = sdk.route("add a test")["decision_id"]
    plan = sdk.execute_dry_run(did)
    assert plan["would_execute"] is False


def test_error_surfaces_as_exception(sdk):
    with pytest.raises(AgentRouterError) as exc:
        sdk.get_decision("d_99999")
    assert exc.value.status_code == 404
    assert exc.value.code == "not_found"


def test_auth_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.setenv("AGENTROUTER_API_KEY", "k3y")
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    server, thread, url = _serve()
    try:
        bad = AgentRouterClient(url)
        with pytest.raises(AgentRouterError) as exc:
            bad.models()
        assert exc.value.status_code == 401
        bad.close()

        good = AgentRouterClient(url, api_key="k3y")
        assert good.models()
        good.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
