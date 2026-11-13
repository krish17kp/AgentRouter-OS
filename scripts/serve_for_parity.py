"""Serve the real AgentRouter API on loopback for cross-language SDK tests.

The TypeScript parity suite can assert the requests its client *builds*, but not
that the server accepts them — a body the real app rejects would still pass a
recorded-transport test. This script closes that gap by starting the genuine
Python (default) or Rust API server in a throwaway home and printing the URL,
so Node can drive it over loopback.

Usage (from Node, not by hand):

    python scripts/serve_for_parity.py
    # stdout, first line: PARITY_SERVER_URL=http://127.0.0.1:<port>

    AGENTROUTER_PARITY_SERVER=rust python scripts/serve_for_parity.py

Serves until terminated. Loopback only, on an ephemeral port, against a fresh
temporary AGENTROUTER_HOME — no external network, no credentials, no paid calls,
and nothing touched in the developer's real ~/.agentrouter.
"""

from __future__ import annotations

import atexit
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

_HOME_PREFIX = "agentrouter-parity-"
_STALE_AFTER_SECONDS = 3600
_RUST_SERVER: subprocess.Popen[bytes] | None = None


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


def _initialize_home(home: Path) -> int:
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
    return 0


def _serve_python(home: Path) -> int:
    if _initialize_home(home) != 0:
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


def _serve_rust(home: Path) -> int:
    global _RUST_SERVER

    if _initialize_home(home) != 0:
        return 1

    executable_name = "agentrouter-api-server.exe" if os.name == "nt" else "agentrouter-api-server"
    executable = Path(__file__).resolve().parents[1] / "target" / "debug" / executable_name
    if not executable.is_file():
        print(
            f"Rust API server binary is missing: {executable}; build the workspace first",
            file=sys.stderr,
        )
        return 1

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    environment = os.environ.copy()
    environment.pop("AGENTROUTER_API_KEY", None)
    _RUST_SERVER = subprocess.Popen(
        [str(executable), "--bind", f"127.0.0.1:{port}", "--home", str(home)],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if _RUST_SERVER.poll() is not None:
            error = (
                _RUST_SERVER.stderr.read().decode("utf-8", errors="replace")
                if _RUST_SERVER.stderr
                else ""
            )
            print(f"Rust API server exited during startup: {error}", file=sys.stderr)
            return 1
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=0.25):
                print(f"PARITY_SERVER_URL={url}", flush=True)
                return _RUST_SERVER.wait()
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)

    print("Rust API server did not become ready within 30 seconds", file=sys.stderr)
    return 1


def _stop_rust_server() -> None:
    global _RUST_SERVER
    if _RUST_SERVER is None:
        return
    if _RUST_SERVER.poll() is None:
        _RUST_SERVER.terminate()
        try:
            _RUST_SERVER.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _RUST_SERVER.kill()
            _RUST_SERVER.wait(timeout=5)
    if _RUST_SERVER.stderr:
        _RUST_SERVER.stderr.close()
    _RUST_SERVER = None


def _serve(home: Path) -> int:
    implementation = os.environ.get("AGENTROUTER_PARITY_SERVER", "python").lower()
    if implementation == "python":
        return _serve_python(home)
    if implementation == "rust":
        return _serve_rust(home)
    print(
        "AGENTROUTER_PARITY_SERVER must be 'python' or 'rust'",
        file=sys.stderr,
    )
    return 2


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
        _stop_rust_server()
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
