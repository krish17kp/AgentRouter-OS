# TASK-142 evidence

The evaluator API probe now serializes all fields from every Rust seed
`ModelEntry`. It writes the effective vendor value through `ModelEntry::vendor`
to match Python's validator default. The Python test compares these values to
each seed model's full `model_dump(mode="json")` and compares Rust exports with
the live Python `evaluators.__all__`.

## Local verification

- `./.venv/bin/python -m pytest -q tests/test_rust_evaluation_evaluators_api_compat.py`:
  1 passed.
- `cargo fmt --all -- --check`: passed.
- `git diff --check`: passed.

The parity row remains Partial because evaluator runtime discovery and
orchestration are not fully represented in Rust.
