# TASK-215 — Diagnostic-bundle database no-follow hardening

## Objective

Keep the Rust diagnostic-bundle data-shape collector from reading a decision
database through a symlink outside the selected AgentRouter home.

## Acceptance

- bundle data-shape inspection uses SQLite no-follow semantics;
- a symlinked database fails closed and does not alter its outside target;
- normal bundle creation and optional snapshot behavior remain unchanged;
- focused bundle tests, formatting, and strict Clippy pass;
- the remaining SQLite handle/sidecar limitations remain documented honestly.
