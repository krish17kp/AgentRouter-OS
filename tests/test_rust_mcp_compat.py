"""Protocol and tool parity checks between Python and Rust MCP servers."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
mcp = pytest.importorskip("mcp", reason="install the optional MCP extra")


def _rust_server_binary() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return ROOT / "target" / "debug" / f"agentrouter-mcp-server{suffix}"


def _initialize_home(path: Path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from agentrouter.cli import app

    path.mkdir()
    monkeypatch.setenv("AGENTROUTER_HOME", str(path))
    monkeypatch.setenv("AGENTROUTER_PLUGIN_ROOT", str(path / "plugins"))
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 0, result.output


async def _session_snapshot(command: str, args: list[str], home: Path) -> dict:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    environment = {**os.environ, "AGENTROUTER_HOME": str(home)}
    environment.pop("AGENTROUTER_API_KEY", None)
    parameters = StdioServerParameters(
        command=command,
        args=args,
        env=environment,
        cwd=ROOT,
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()

            async def call(name: str, arguments: dict | None = None):
                result = await session.call_tool(name, arguments)
                return {
                    "structured": result.structuredContent,
                    "is_error": result.isError,
                    "text": [item.text for item in result.content if item.type == "text"],
                }

            outputs = {
                "classify": await call(
                    "classify", {"task": "write a short guide", "context_tokens": 512}
                ),
                "models": await call("list_models"),
                "hosts": await call("list_hosts"),
            }
            outputs["route"] = await call("route", {"task": "summarize a technical report"})
            route_value = outputs["route"]["structured"]
            assert isinstance(route_value, dict), outputs["route"]
            decision_id = route_value.get("decision_id")
            assert decision_id
            outputs["explain"] = await call("explain", {"decision_id": decision_id})
            outputs["unknown"] = await call("not_a_tool")

            return {
                "protocol_version": initialized.protocolVersion,
                "server_name": initialized.serverInfo.name,
                "capabilities": initialized.capabilities.model_dump(mode="json", exclude_none=True),
                "tools": [
                    {
                        key: value
                        for key, value in tool.model_dump(
                            mode="json", by_alias=True, exclude_none=True
                        ).items()
                        if key in {"name", "description", "inputSchema", "outputSchema"}
                    }
                    for tool in listed.tools
                ],
                "outputs": outputs,
            }


def _without_timestamps(value):
    if isinstance(value, dict):
        return {
            key: _without_timestamps(item)
            for key, item in value.items()
            if key not in {"created_at", "updated_at", "timestamp"}
        }
    if isinstance(value, list):
        return [_without_timestamps(item) for item in value]
    return value


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
def test_rust_mcp_matches_python_protocol_tools_and_results(tmp_path, monkeypatch):
    binary = _rust_server_binary()
    if not binary.is_file():
        subprocess.run(
            ["cargo", "build", "--locked", "-p", "agentrouter-mcp"], cwd=ROOT, check=True
        )
    assert binary.is_file()

    python_home = tmp_path / "python-home"
    rust_home = tmp_path / "rust-home"
    _initialize_home(python_home, monkeypatch)
    _initialize_home(rust_home, monkeypatch)

    python_snapshot = asyncio.run(
        _session_snapshot(sys.executable, ["-m", "agentrouter.mcp_server"], python_home)
    )
    rust_snapshot = asyncio.run(
        _session_snapshot(str(binary), ["--home", str(rust_home)], rust_home)
    )

    assert python_snapshot["protocol_version"] == rust_snapshot["protocol_version"] == "2025-11-25"
    assert python_snapshot["server_name"] == rust_snapshot["server_name"] == "agentrouter"
    assert python_snapshot["capabilities"] == rust_snapshot["capabilities"]
    assert [tool["name"] for tool in rust_snapshot["tools"]] == [
        "route",
        "classify",
        "explain",
        "list_models",
        "list_hosts",
    ]
    assert python_snapshot["tools"] == rust_snapshot["tools"]

    for name in ("classify", "models", "hosts", "route", "explain"):
        assert python_snapshot["outputs"][name]["is_error"] is False
        assert rust_snapshot["outputs"][name]["is_error"] is False
        assert _without_timestamps(
            python_snapshot["outputs"][name]["structured"]
        ) == _without_timestamps(rust_snapshot["outputs"][name]["structured"]), name
    assert python_snapshot["outputs"]["unknown"]["is_error"] is True
    assert rust_snapshot["outputs"]["unknown"]["is_error"] is True
