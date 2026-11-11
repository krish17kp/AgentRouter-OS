# TASK-045: Rust evaluation package facade

Ported the public `agentrouter.evaluation` package surface as
`agentrouter_evaluation::evaluation_api`, re-exporting the same three public
types. A Python/Rust test compares the `__all__` export contract exactly.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_context_bands_compat.py
  tests/test_rust_evaluation_package_api_compat.py`: 4 passed locally.
- `cargo fmt --all -- --check` and evaluation-crate Clippy with warnings denied:
  passed locally.
- Linux/Windows/macOS hosted checks for the Rust compatibility matrix start
  after the RC push.
