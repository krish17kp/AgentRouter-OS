# TASK-046: Rust annotation package facade

The Python package exports `SCHEMA_VERSION`, `CATEGORIES`, and `SPLITS`. The
Rust `annotation_api` facade re-exports the same constants from the annotation
schema module; a Python/Rust differential test compares the complete values and
ordering.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_annotation_package_api_compat.py`:
  1 passed locally.
- `cargo test -p agentrouter-evaluation --locked`, formatting, and Clippy with
  warnings denied: passed locally.
- Linux/Windows/macOS hosted Rust/Python compatibility CI starts on the RC push.
