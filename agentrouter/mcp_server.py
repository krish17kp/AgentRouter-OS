"""MCP server exposing AgentRouter's safe read/route/explain tools (TASK-005 / backlog L2).

A thin adapter over ``agentrouter.server.service`` so agents/IDEs can call routing over
the Model Context Protocol without shelling out to the CLI. It is **read-only and dry-run
by design**: there is deliberately NO execute tool — nothing here ever spawns a process or
runs a model. The tool functions are plain callables (testable without the MCP runtime);
``build_server`` registers them on a FastMCP instance, imported lazily so the core package
never hard-depends on ``mcp``.

Run: ``agentrouter mcp``  (install extras first: ``pip install "agentrouter-os[mcp]"``)
"""

from __future__ import annotations

from typing import Any

from .server import service

SERVER_NAME = "agentrouter"


def route(
    task: str,
    prefer: str | None = None,
    context_tokens: int | None = None,
    risk: str | None = None,
    tools: list[str] | None = None,
) -> dict[str, Any]:
    """Classify a task and recommend the best model/tool, with rationale.

    Dry-run only: returns the plan and a decision id; never executes anything.
    """
    return service.route_task(
        task, prefer=prefer, context_tokens=context_tokens, risk=risk, tools=tools
    )


def classify(
    task: str,
    context_tokens: int | None = None,
    risk: str | None = None,
    tools: list[str] | None = None,
) -> dict[str, Any]:
    """Classify a task across the 7 dimensions (type/complexity/risk/context/...)."""
    return service.classify_task(task, context_tokens=context_tokens, risk=risk, tools=tools)


def explain(decision_id: str) -> dict[str, Any] | None:
    """Return a previously logged routing decision by id, or null if unknown."""
    return service.get_decision(decision_id)


def list_models() -> list[dict[str, Any]]:
    """List the model catalog (vendor, id, release channel, context, host availability)."""
    return service.list_models()


def list_hosts() -> list[dict[str, Any]]:
    """List known execution hosts and their availability (read-only; runs nothing)."""
    return service.list_hosts()


# Read/route/explain surface only — intentionally excludes any execute tool.
TOOLS = (route, classify, explain, list_models, list_hosts)


def build_server():
    """Build the FastMCP server with the safe tools registered. Requires the mcp extra."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:  # pragma: no cover - exercised via the CLI error path
        raise RuntimeError(
            'MCP extras not installed. Run: pip install "agentrouter-os[mcp]"'
        ) from e
    server = FastMCP(SERVER_NAME)
    for fn in TOOLS:
        server.tool()(fn)
    return server


def main() -> None:  # pragma: no cover - stdio loop, exercised manually / in integration
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
