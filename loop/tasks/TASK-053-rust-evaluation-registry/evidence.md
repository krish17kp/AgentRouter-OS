# TASK-053: Rust evaluation dataset registry facade

Added Rust registry functions for ordered dataset names, adapter descriptors,
best-effort lookup, available adapter manifests, and profile selection. A
Python/Rust differential test compares the full name/profile order and unknown
dataset behavior. Adapter construction and optional remote dataset loading
remain partial.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_evaluation_registry_api_compat.py`:
  1 passed locally.
- `cargo test -p agentrouter-evaluation --locked`, formatting, and evaluation
  crate Clippy with warnings denied: passed locally.
- Hosted Linux/Windows/macOS compatibility checks follow the RC push.
