# TASK-179 — Evaluation `prepare --all` exit parity

## Contract

Keep the Rust `agentrouter-evaluate prepare` command contract-compatible with
Python's `agentrouter evaluate prepare` command. A single unavailable dataset is
an honest `SKIPPED_EXTERNAL` failure, while `--all` is a report over every
registered dataset and exits successfully when all sources are unavailable.

## Scope

- preserve fail-closed external-data reporting and exact blocker text;
- return exit code 1 for one explicitly requested dataset that cannot be
  prepared;
- return exit code 0 for `--all` when the report completes, even if every
  dataset is externally blocked;
- report a successfully prepared dataset as `REAL` if a future Rust loader is
  enabled.

The evaluation CLI remains Partial overall because real dataset loading and
runtime orchestration are still intentionally external/unfinished.
