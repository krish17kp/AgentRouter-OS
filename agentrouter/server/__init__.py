"""Local REST API surface for AgentRouter OS (Phase P7).

Intentionally does NOT re-export the FastAPI app here: importing a sibling module
such as ``service`` (as the MCP server does) must not drag in FastAPI. Import the
REST app directly from its submodule when you need it:

    from agentrouter.server.app import app, create_app
"""

from __future__ import annotations
