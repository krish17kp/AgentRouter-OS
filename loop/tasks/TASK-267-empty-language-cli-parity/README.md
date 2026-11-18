# TASK-267 — empty language option parity

## Outcome

Rust `agentrouter-evaluate run --languages ""` now treats the empty value as
an omitted filter, matching Python's Typer parsing. Non-empty comma lists keep
their existing trimmed entries.

## Evidence

- Rust evaluation CLI and registered-runner compatibility selection: 44 passed.
- `cargo fmt --all` passed.
- The regression compares the complete MASSIVE fixture report with Python.

## Scope boundary

This is a CLI parsing parity fix only. External benchmark access, human
context-band adjudication, hosted promotion, and deployment remain open.
