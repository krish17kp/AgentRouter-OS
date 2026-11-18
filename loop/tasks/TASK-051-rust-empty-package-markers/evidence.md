# TASK-051: Empty package initializer contracts

`agentrouter.evaluation.adapters` and `agentrouter.server` are documentation-only
package initializers with no public runtime exports. Added Rust package marker
constants and a differential test asserting that both Python modules and the
Rust facade expose empty symbol lists. The implementation modules remain
separate migration work.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_empty_package_markers_compat.py
  tests/test_rust_annotation_schema_compat.py`: 24 passed locally.
- `cargo test -p agentrouter-evaluation --locked`, formatting, and evaluation
  crate Clippy with warnings denied: passed locally.
- Cross-platform compatibility CI starts after the RC push.
