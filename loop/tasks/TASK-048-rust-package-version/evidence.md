# TASK-048: Rust distribution version parity

Added `agentrouter_core::package_version`, sourced from the canonical Python
distribution metadata in `pyproject.toml`, plus a differential test against
`agentrouter.__version__`. This avoids maintaining a second version literal.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_package_version_compat.py`:
  1 passed locally.
- `cargo test -p agentrouter-core --locked`, formatting, and core-crate Clippy
  with warnings denied: passed locally.
- Linux/Windows/macOS hosted Rust/Python compatibility CI follows the RC push.
