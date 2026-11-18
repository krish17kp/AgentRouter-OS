"""SDK ↔ HTTP contract parity (TASK-018A).

The capability manifest (contracts/sdk/capabilities.json) is only a claim; this
module turns it into evidence. Every operation it lists is:

* checked to exist in the committed OpenAPI contract,
* checked to exist as a method on both SDK clients,
* and actually **called** against the real AgentRouter ASGI app.

Listing an operation without exercising it would be a fake claim of support, so
the manifest and the exercised set are asserted to be equal.

The server runs in-process on loopback (uvicorn, port 0) — the real app, no
external network, no provider credentials and no paid calls.
"""

from __future__ import annotations

import inspect
import json
import re
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

import uvicorn  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from agentrouter import contract  # noqa: E402
from agentrouter.cli import app as cli_app  # noqa: E402
from agentrouter.sdk import AgentRouterClient, AgentRouterError  # noqa: E402
from agentrouter.server.app import create_app  # noqa: E402

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = json.loads(
    (REPO_ROOT / "contracts" / "sdk" / "capabilities.json").read_text(encoding="utf-8")
)
TS_SOURCE = (REPO_ROOT / "sdk" / "typescript" / "src" / "index.ts").read_text(encoding="utf-8")

# Operations this module actually calls; compared against the manifest at the end.
EXERCISED: set[str] = set()


def _serve():
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 30
    while not server.started and time.time() < deadline:
        time.sleep(0.01)
    assert server.started, "in-process server did not start"
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, f"http://127.0.0.1:{port}"


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    import os

    prev_home = os.environ.get("AGENTROUTER_HOME")
    prev_key = os.environ.get("AGENTROUTER_API_KEY")
    os.environ["AGENTROUTER_HOME"] = str(home)
    os.environ.pop("AGENTROUTER_API_KEY", None)
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    server, url = _serve()
    try:
        yield url
    finally:
        server.should_exit = True
        if prev_home is None:
            os.environ.pop("AGENTROUTER_HOME", None)
        else:
            os.environ["AGENTROUTER_HOME"] = prev_home
        if prev_key is not None:
            os.environ["AGENTROUTER_API_KEY"] = prev_key


@pytest.fixture()
def client(live):
    c = AgentRouterClient(live)
    yield c
    c.close()


# --- manifest integrity ------------------------------------------------------


def test_every_manifest_operation_exists_in_the_http_contract():
    doc = contract.load_baseline(REPO_ROOT)
    for op in CAPABILITIES["operations"]:
        assert op["path"] in doc["paths"], f"{op['id']}: path missing from contract"
        assert op["method"] in doc["paths"][op["path"]], f"{op['id']}: method missing"


def test_manifest_covers_every_contract_operation():
    """No served operation may be silently missing from the SDK manifest."""
    doc = contract.load_baseline(REPO_ROOT)
    served = {
        (p, m)
        for p, ops in doc["paths"].items()
        for m in ops
        if m in ("get", "post", "put", "patch", "delete")
    }
    claimed = {(op["path"], op["method"]) for op in CAPABILITIES["operations"]}
    assert served == claimed


def test_python_sdk_implements_every_claimed_method():
    for op in CAPABILITIES["operations"]:
        method = getattr(AgentRouterClient, op["python"], None)
        assert callable(method), f"{op['id']}: AgentRouterClient.{op['python']} missing"


def test_typescript_sdk_implements_every_claimed_method():
    for op in CAPABILITIES["operations"]:
        name = op["typescript"]
        assert re.search(rf"\b{re.escape(name)}\s*\(", TS_SOURCE), (
            f"{op['id']}: TypeScript method {name}() missing"
        )


def test_both_sdks_target_the_same_paths():
    """A path present in one SDK but not the other is a parity break."""
    for op in CAPABILITIES["operations"]:
        literal = op["path"].split("{")[0]
        assert literal in TS_SOURCE, f"{op['id']}: TypeScript SDK does not use {literal}"
        py = inspect.getsource(getattr(AgentRouterClient, op["python"]))
        assert literal in py, f"{op['id']}: Python SDK does not use {literal}"


# --- every operation exercised against the real app --------------------------


def test_health_and_ready(client):
    assert client.health()["status"] == "ok"
    assert client.ready()["status"] == "ready"
    EXERCISED.update({"health", "ready"})


def test_models_and_hosts(client):
    models = client.models()
    assert isinstance(models, list) and models
    assert {"model_id", "key", "host_availability"} <= set(models[0])

    hosts = client.hosts()
    assert isinstance(hosts, list) and hosts
    # additive host-state fields (TASK-016) must reach SDK clients
    assert {"host", "availability", "reason", "state"} <= set(hosts[0])
    assert "remedy" in hosts[0]
    EXERCISED.update({"models", "hosts"})


def test_classify_route_decision_feedback_dry_run(client):
    classified = client.classify("write a haiku about routers")
    assert "task_type" in classified

    routed = client.route("write a haiku about routers")
    assert "recommended" in routed or "decision_id" in routed
    decision_id = routed.get("decision_id")
    assert decision_id, "route must return a decision id when logging is on"

    fetched = client.get_decision(decision_id)
    assert fetched

    assert client.feedback(decision_id, 5, "worked")["recorded"] is True

    plan = client.execute_dry_run(decision_id)
    assert plan
    EXERCISED.update({"classify", "route", "get_decision", "feedback", "execute_dry_run"})


def test_route_no_log_is_sent_as_an_explicit_false(client):
    """Body cleaning must keep explicit False (parity rule), not drop it."""
    routed = client.route("summarize a PDF", no_log=True)
    assert routed.get("decision_id") is None or routed.get("decision_id") == ""


# --- shared behaviours -------------------------------------------------------


def test_error_envelope_surfaces_as_typed_error(client):
    with pytest.raises(AgentRouterError) as excinfo:
        client.get_decision("d_does_not_exist")
    assert excinfo.value.status_code == 404
    assert excinfo.value.code == "not_found"


def test_validation_error_is_typed(client):
    with pytest.raises(AgentRouterError) as excinfo:
        client.feedback("d_00001", 99)  # rating out of range
    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "validation_error"


def test_request_id_header_is_returned(live):
    import httpx

    r = httpx.get(f"{live}/health", timeout=10)
    assert r.headers.get("X-Request-ID")


def test_internal_error_is_a_typed_envelope_with_a_request_id(monkeypatch):
    """No raw traceback may reach a client, and the failure must be correlatable."""
    from fastapi.testclient import TestClient

    from agentrouter.server import service

    application = create_app()
    monkeypatch.setattr(
        service, "list_models", lambda: (_ for _ in ()).throw(RuntimeError("boom /home/u/.env"))
    )
    with TestClient(application, raise_server_exceptions=False) as tc:
        r = tc.get("/v1/models")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert r.headers.get("X-Request-ID")
    assert "boom" not in r.text and ".env" not in r.text


def test_auth_header_is_required_when_a_key_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.setenv("AGENTROUTER_API_KEY", "secret-key")
    assert runner.invoke(cli_app, ["init"]).exit_code == 0
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as tc:
        assert tc.get("/v1/models").status_code == 401
        assert tc.get("/v1/models", headers={"X-API-Key": "secret-key"}).status_code == 200
        # the key itself must never be echoed back in an error body
        body = tc.get("/v1/models", headers={"X-API-Key": "wrong"}).text
        assert "secret-key" not in body


def test_non_json_error_body_still_raises_typed_error():
    """A proxy/gateway may answer HTML; both SDKs must not raise a parse error."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>bad gateway</html>")

    c = AgentRouterClient("http://x", transport=httpx.MockTransport(handler))
    with pytest.raises(AgentRouterError) as excinfo:
        c.health()
    assert excinfo.value.status_code == 502
    assert excinfo.value.code == "error"


def test_python_sdk_timeout_is_configurable():
    c = AgentRouterClient("http://127.0.0.1:1", timeout=0.25)
    assert c._client.timeout.connect == pytest.approx(0.25)
    c.close()


def test_typescript_sdk_declares_matching_behaviours():
    """Parity of the documented behaviours, checked in the TS source."""
    assert "X-API-Key" in TS_SOURCE
    assert "timeoutMs" in TS_SOURCE
    assert "AgentRouterError" in TS_SOURCE
    assert "no_log" in TS_SOURCE  # explicit false is sent, matching Python
    # defensive JSON parse so a non-JSON error body cannot throw a SyntaxError
    assert "JSON.parse" in TS_SOURCE and "catch" in TS_SOURCE


def test_manifest_operations_were_all_exercised(client):
    """Guards against a manifest entry that is claimed but never called."""
    # ensure the exercising tests have run in this module
    test_health_and_ready(client)
    test_models_and_hosts(client)
    test_classify_route_decision_feedback_dry_run(client)
    claimed = {op["id"] for op in CAPABILITIES["operations"]}
    assert claimed == EXERCISED, f"not exercised: {sorted(claimed - EXERCISED)}"
