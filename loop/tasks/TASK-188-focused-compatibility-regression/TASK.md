# TASK-188 — Focused compatibility regression

## Objective

Run the current release-candidate changes through the Python/Rust compatibility
surfaces most directly affected by the SDK, reliability, plugin, and
diagnostics work.

## Acceptance

- SDK compatibility tests pass;
- reliability compatibility tests pass;
- plugin compatibility tests pass;
- diagnostics compatibility tests pass;
- the run uses an isolated environment and records the exact count.
