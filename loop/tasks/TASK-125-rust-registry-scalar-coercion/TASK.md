# TASK-125 — Rust registry scalar coercion

## Objective

Match the Python/Pydantic registry's scalar coercion and rejection behavior in
Rust, including when registry records are streamed from JSON with
`serde_json`'s `arbitrary_precision` feature enabled.

## Changes

- Added Pydantic-compatible integer, float, and boolean coercion for registry
  fields and differential cases for accepted and rejected values.
- Replaced the derived untagged scalar enum with a custom deserializer that
  handles `serde_json` arbitrary-precision number tokens.
- Reject the deserializer's private number marker in YAML registry documents so
  it cannot be used as user-supplied scalar data.

## Verification

- Registry and evaluation Python/Rust differential suites: 108 passed.
- Full Python coverage suite: 2,332 passed, 4 skipped; 91.983% statement,
  87.735% branch, 91.008% combined.
- Full Rust workspace tests: passed.
- Strict Clippy, Rust formatting, full Ruff check/format, and `git diff --check`:
  passed.
- Hosted CI for the repair: pending push. Cross-platform jobs on the previous
  pushed commit exposed the streaming-number regression.

## Release status

This task fixes a compatibility regression but does not complete Rust migration
or release readiness. PR #16 remains blocked by the unchanged frozen context
score of 0.6667 against 0.90. The required human annotation round, credentialed
OpenAI smoke, deployment inputs, and final owner-authorized promotion remain
open.
