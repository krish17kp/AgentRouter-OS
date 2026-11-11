# TASK-047: Rust evaluator package facade and seed loading

Implemented `evaluators_api` with all seven Python package exports and added
embedded, validated seed catalog loading through the existing Rust registry
parsers. The focused compatibility test compares the complete seed model
identity order and the public export list. Underlying evaluator runtime
discovery is still incomplete, so the parity matrix remains Partial.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_evaluation_evaluators_api_compat.py`:
  passed locally; it compares all 81 packaged model identities/orderings and
  the seven public exports against Python.
- `cargo test -p agentrouter-evaluation --offline`, Rust formatting, and
  evaluation-crate Clippy with warnings denied: passed locally.
- The evaluator package remains **Partial** because runtime introspection and
  orchestration in several re-exported Python evaluator functions is not yet
  ported.
- Linux/Windows/macOS hosted CI starts after the RC push.
