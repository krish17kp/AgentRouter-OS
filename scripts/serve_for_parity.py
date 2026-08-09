"""Serve the real AgentRouter app on loopback so a non-Python SDK can be tested against it.

The TypeScript parity suite can assert the requests its client *builds*, but not
that the server accepts them — a body the real app rejects would still pass a
recorded-transport test. This script closes that gap by starting the genuine
ASGI app in a throwaway home and printing the URL, so Node can drive it over
loopback.

Usage (from Node, not by hand):

    python scripts/serve_for_parity.py
    # stdout, first line: PARITY_SERVER_URL=http://127.0.0.1:<port>

Serves until terminated. Loopback only, on an ephemeral port, against a fresh
temporary AGENTROUTER_HOME — no external network, no credentials, no paid calls,
and nothing touched in the developer's real ~/.agentrouter.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    home = Path(tempfile.mkdtemp(prefix="agentrouter-parity-"))
    os.environ["AGENTROUTER_HOME"] = str(home)
    # Auth off: parity covers the authenticated path in the Python suite, where
    # the key can be set without leaking it into a child process's environment.
    os.environ.pop("AGENTROUTER_API_KEY", None)

    from typer.testing import CliRunner

    from agentrouter.cli import app as cli_app

    result = CliRunner().invoke(cli_app, ["init"])
    if result.exit_code != 0:
        print(f"agentrouter init failed: {result.output}", file=sys.stderr)
        return 1

    import uvicorn

    from agentrouter.server.app import create_app

    config = uvicorn.Config(create_app(), host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)

    # uvicorn binds before serving, so the socket exists by the time the startup
    # hook runs — that is the first moment the real port is knowable.
    original_startup = server.startup

    async def startup(sockets=None):  # type: ignore[override]
        await original_startup(sockets=sockets)
        port = server.servers[0].sockets[0].getsockname()[1]
        print(f"PARITY_SERVER_URL=http://127.0.0.1:{port}", flush=True)

    server.startup = startup  # type: ignore[method-assign]
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
