# TASK-110 — safe Rust plugin installation

## Objective

Port the non-forced plugin install cases to the unified Rust CLI while keeping
the Python installer as the shipping authority. Install only missing files,
record byte-identical files as pre-existing or explicitly adopted, and skip an
unchanged managed file. Do not replace differing files, perform managed
upgrades, recover transactions, or remove user data from the Rust path until
those protocols are ported and independently verified.

## Contract cases

- Create a missing Codex file and ownership record; repeat idempotently; prove
  the Python reader accepts the state and Python uninstall removes the exact
  Rust-managed file.
- Install Claude Code and prove the created cleanup directory is recorded and
  safely removed by Python uninstall.
- Preserve byte-identical pre-existing content on uninstall by default; with
  `--adopt-identical`, record ownership so Python uninstall removes it.
- Refuse differing user-authored content, `--force`, linked state paths, and
  managed file changes without overwriting those paths.
- Compare serialized ownership state byte-for-byte with Python's serializer;
  keep file paths and identities compatible on Windows as well as Unix.

## Verification

Full Python and Rust suites, focused Python/Rust plugin differential tests,
strict workspace Clippy, formatting, Ruff, hosted Linux/Windows/macOS Python
and Rust jobs, and the immutable release-gate result are tracked in
`EVIDENCE.md`.

## Remaining scope

Forced replacement, transaction recovery, Rust uninstall, and complete Rust
plugin parity remain open. The Rust install command must give an accurate
message about uninstall still being Python-only.
