# TASK-238 — Evaluation prepare unknown-dataset parity

## Objective

Align Rust evaluation `prepare` with Python when an unknown dataset name is
requested: report the adapter as unavailable and return the normal readiness
status instead of surfacing a registry lookup error.

## Acceptance

- an unknown single-dataset request prints `UNAVAILABLE (adapter not importable)`;
- the request exits 1, matching Python's unavailable-adapter contract;
- JSON output remains machine-readable;
- focused Python/Rust compatibility, Rust tests, Clippy, formatting, and diff
  checks pass.
