# TASK-271 — negative soak-count parity

## Outcome

Rust `agentrouter reliability soak` now preserves Python's shipped behavior
for negative `--workers` and `--batch` values: both become empty ranges and
the command reports zero cycles/requests instead of rejecting the options.

## Evidence

- `tests/test_rust_reliability_compat.py`: 13 passed.
- `cargo clippy -p agentrouter-cli --all-targets --all-features -- -D warnings`:
  passed.
- `cargo fmt --all`: passed.

## Scope boundary

This is CLI migration parity. It does not alter the release gate, live smoke,
human evaluation, or deployment approval requirements.
