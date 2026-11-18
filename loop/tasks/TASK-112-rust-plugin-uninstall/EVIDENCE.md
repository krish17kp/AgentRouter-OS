# TASK-112 evidence

## Local implementation and verification

- Rust exposes `agentrouter plugin uninstall NAME` and removes a destination
  only after matching the recorded digest and filesystem identity. It restores
  Python-created backups only after checking bytes, identity, and mode; retains
  edited, linked, ambiguous, and concurrent files; and handles old manifest
  paths and identity-matched empty cleanup directories.
- Python and Rust doctor output now direct interrupted-transaction recovery to
  `python -m agentrouter plugin install NAME`. Rust uninstall refuses a
  journaled transaction without deleting or changing the journal.
- Focused plugin safety, platform, decisions, faults, and Rust/Python
  compatibility suites: **230 passed, 3 skipped**.
- Full Python regression with coverage: **2,237 passed, 4 skipped**;
  92.83% line, 88.63% branch, and 91.87% combined coverage.
- Rust workspace: **153 passed** across 124 test suites; strict Clippy passes.
  `cargo fmt --check`, Ruff check and format, `git diff --check`, and
  `cargo audit` pass.
- The Rust CLI crate has **53 passing unit tests**. New regressions cover a
  backup whose payload no longer matches its ownership record, interrupted
  backup restoration, unsafe staging-parent permissions, private state
  directory permissions, and a concurrently created cleanup directory.
- The Windows rename helper type-checks in an isolated Windows-target build.
  Full CLI cross-compilation on this host stops before project Rust code because
  the MinGW C compiler required by bundled SQLite and ring is unavailable.

## Hosted validation

Pending the authorized push to `release/agentrouter-v0.5-rc1` and hosted
Linux/Windows/macOS checks. Force replacement and Rust-side interrupted
transaction recovery remain outside this task. The frozen context-band gate
and human annotation requirements are unchanged.
