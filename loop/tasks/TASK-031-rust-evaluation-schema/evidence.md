# TASK-031 — Rust evaluation schema parity

## Contract covered

The Rust crate's evaluation case, provenance, expected-label, routing, and
safety types now cover the Python schema's public serialization methods and
validation behavior in the differential suite. The Rust schema probe also
returns the Python-compatible normalized task hash and `with_checksum()` result.

## Differential evidence

- Full and default `EvaluationCase` serialization matches Python, including
  Unicode text and nested expected/routing/safety/provenance fields.
- Exact task hashes and checksummed copies match Python.
- Empty tasks, unknown fields, invalid enum values, and wrong task types are
  rejected by Rust.
- Focused schema differential test, Rust workspace, Clippy, format, Ruff, and
  diff checks pass locally. Hosted CI is still running for the current RC head.
