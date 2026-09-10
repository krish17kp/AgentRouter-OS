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

import atexit
import os
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path

_HOME_PREFIX = "agentrouter-parity-"
_STALE_AFTER_SECONDS = 3600


def _sweep_stale_homes() -> None:
    """Remove homes an earlier run could not clean up.

    SIGKILL is uncatchable, so a hard kill always leaks one directory. Rather
    than claim cleanup is total, bound the leak: anything older than an hour
    cannot belong to a live parity run, which finishes in seconds. Only our own
    prefix inside the system temp dir is ever considered.
    """
    now = time.time()
    for path in Path(tempfile.gettempdir()).glob(f"{_HOME_PREFIX}*"):
        try:
            if path.is_dir() and now - path.stat().st_mtime > _STALE_AFTER_SECONDS:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:  # pragma: no cover - racing another sweeper is fine
            continue


def _serve(home: Path) -> int:
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


def main() -> int:
    """Serve until terminated, and take the throwaway home with us on the way out.

    The temp home is a real registry and decision store, so leaving one behind
    per run leaks state into /tmp indefinitely. Cleanup has to survive the way
    this process actually dies: the Node harness sends SIGTERM, CI may send
    SIGINT, and an exception can unwind at any point — so the handler is
    registered for all three rather than relying on a `finally` that a default
    SIGTERM disposition would skip entirely.
    """
    _sweep_stale_homes()
    home = Path(tempfile.mkdtemp(prefix="agentrouter-parity-"))

    def cleanup(*_args: object) -> None:
        shutil.rmtree(home, ignore_errors=True)

    atexit.register(cleanup)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, lambda *_a: sys.exit(0))  # unwinds -> atexit runs
        except (ValueError, OSError):  # pragma: no cover - non-main thread/platform
            pass

    try:
        return _serve(home)
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
