# TASK-268 — negative numeric evaluation CLI values

## Outcome

Rust evaluation CLI numeric options now accept negative integers, matching
Python's Typer parsing. `--limit -1` therefore reaches deterministic sampling
and reports an empty sample instead of being misread as a missing value.

## Evidence

- `tests/test_rust_evaluation_cli_compat.py`: 25 passed.
- The new differential regression compares the complete negative-limit report
  with Python.
- `cargo fmt --all`: passed.

## Scope boundary

This is CLI parsing parity only. Release remains held by the frozen
context-band gate and external credentials/approval requirements.
