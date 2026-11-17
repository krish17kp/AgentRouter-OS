# TASK-201 — Python-absent Rust runtime validation

## Objective

Exercise the optimized Rust runtime with Python-related environment variables
removed, proving the core CLI, planning, diagnostics, and MCP paths do not
silently depend on the Python package.

## Acceptance

- fresh isolated home initializes and saves a route;
- read-only `plan` reports `execution_enabled: false`;
- `doctor --json` succeeds without Python environment variables;
- MCP initialize negotiates the current protocol and reports the RC version.
