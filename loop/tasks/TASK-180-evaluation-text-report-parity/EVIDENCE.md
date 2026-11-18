# TASK-180 evidence

- `cargo fmt --all` passes.
- `cargo test --locked -p agentrouter-evaluation` passes (9 crate tests).
- `cargo clippy --locked -p agentrouter-evaluation --all-targets -- -D warnings`
  passes.
- Direct `context-band-generalization` output now includes the bootstrap CI,
  Python-style list/dict formatting, an unquoted checksum, and signed delta.
- `tests/test_rust_evaluation_cli_compat.py` adds a regression assertion for
  the human-readable contract; the checkout's `.venv` lacks pytest, so the
  Python test executes in the hosted CI matrix.
