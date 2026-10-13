# Repair loop — TASK-005 (1 iteration)

1. crit-4 FAIL (verification): [mcp] extra not standalone — importing mcp_server dragged in
   fastapi via server/__init__.py's eager app re-export.
   - root cause: `from .app import app, create_app` in agentrouter/server/__init__.py.
   - first attempt: PEP-562 lazy __getattr__ -> RecursionError (submodule name `app` collides
     with re-exported symbol; `from . import app` re-enters __getattr__).
   - final fix: delete the re-export (unused — all callers import agentrouter.server.app
     directly). __init__ is now docstring-only.
   - regression: test_mcp_import_does_not_require_fastapi (subprocess with fastapi absent).
   - re-verify: 426 passed; ruff clean.

Not fixed (out of scope / pre-existing): Typer strips `[mcp]` bracket from --help (cosmetic,
affects `server` too); route() unbounded local persistence (LOW, acceptable for local stdio).
