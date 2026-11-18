# TASK-143 evidence

The `agentrouter` binary now exposes a private `__evaluation_surface` JSON
command listing its dispatched commands and groups. `agentrouter-evaluate
run --all` queries this sibling manifest and supplies the discovered names to
the platform evaluator. If the sibling executable is missing or returns invalid
JSON, the full evaluation fails instead of producing a partial scorecard from
placeholder names.

## Local verification

- `./.venv/bin/python -m pytest -q tests/test_rust_evaluation_platform_runtime.py tests/test_rust_evaluation_evaluators_api_compat.py`:
  2 passed.
- `cargo fmt --all -- --check`: passed.
- Strict Clippy for the CLI and evaluation crates: passed.
- `git diff --check`: passed.

The platform calculation is verified against the actual installed manifest.
The evaluation crate and CLI have other documented Partial parity rows.
