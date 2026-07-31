"""TASK-005 — MCP server tools (backlog L2).

Tests the plain tool callables (no MCP runtime needed) plus the safety invariant that
the exposed surface is read/route/explain only — never an execute tool.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from typer.testing import CliRunner

from agentrouter import mcp_server
from agentrouter.cli import app as cli_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    assert runner.invoke(cli_app, ["init"]).exit_code == 0


# ---- safety invariant ----


def test_no_execute_tool_exposed():
    names = {fn.__name__ for fn in mcp_server.TOOLS}
    assert names == {"route", "classify", "explain", "list_models", "list_hosts"}
    assert not any("exec" in n or "run" in n for n in names)


def test_build_server_registers_only_safe_tools():
    pytest.importorskip("mcp")  # build_server needs the optional [mcp] extra
    server = mcp_server.build_server()
    tools = server._tool_manager.list_tools()
    reg = {t.name for t in tools}
    assert reg == {"route", "classify", "explain", "list_models", "list_hosts"}


# ---- tool behavior ----


def test_route_returns_plan_without_executing():
    out = mcp_server.route("summarize a PR")
    assert "recommendation" in out
    assert out.get("decision_id")  # persisted -> explain-able
    # dry-run: no execution result / no spawned process is represented
    assert "would_execute" not in out


def test_classify_returns_dimensions():
    out = mcp_server.classify("refactor the auth module")
    assert out["task_type"] and out["risk"]


def test_explain_roundtrips_a_routed_decision():
    routed = mcp_server.route("write unit tests for the parser")
    did = routed["decision_id"]
    got = mcp_server.explain(did)
    assert got is not None
    assert mcp_server.explain("d_does_not_exist") is None


def test_list_models_and_hosts():
    models = mcp_server.list_models()
    assert models and {"vendor", "model_id"} <= models[0].keys()
    assert isinstance(mcp_server.list_hosts(), list)


def test_mcp_import_does_not_require_fastapi():
    # The [mcp] extra pulls in only `mcp`, not fastapi. Importing the MCP module and
    # its tool callables must work with FastAPI absent (server/__init__ stays lazy).
    code = (
        "import sys; sys.modules['fastapi'] = None\n"
        "import agentrouter.mcp_server as m\n"
        "assert [f.__name__ for f in m.TOOLS] == "
        "['route','classify','explain','list_models','list_hosts']\n"
        "print('ok')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_mcp_cli_command_registered():
    # `agentrouter mcp --help` resolves (build_server not invoked under --help).
    result = runner.invoke(cli_app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "read/route/explain" in result.output
