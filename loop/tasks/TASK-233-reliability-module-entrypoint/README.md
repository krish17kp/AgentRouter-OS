# TASK-233 — Reliability package entrypoint

## Objective

Expose the Python soak profile through the package-level module invocation and
cover the command surface with a subprocess smoke test.

## Acceptance

- `python -m agentrouter.reliability --help` exits successfully;
- the package entrypoint exposes the same soak options as the existing module;
- the focused Python/Rust reliability differential remains green.
