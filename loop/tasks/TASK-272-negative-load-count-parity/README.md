# TASK-272 — negative load-count parity

## Outcome

Rust reliability JSON load probes now preserve Python's behavior for negative
`total` and `workers` counts: both produce an empty load rather than rejecting
the request or attempting a transport call.

## Evidence

- `tests/test_rust_reliability_compat.py`: **15 passed**.
- `cargo fmt --all -- --check`: passed.
- `cargo clippy -p agentrouter-reliability --all-targets --all-features -- -D warnings`: passed.
- `cargo test -p agentrouter-reliability --locked`: 3 passed.

## Scope boundary

This closes a reliability harness input-parity edge. It does not alter the
release gate, live smoke, human evaluation, hosted approval, or deployment
requirements.
