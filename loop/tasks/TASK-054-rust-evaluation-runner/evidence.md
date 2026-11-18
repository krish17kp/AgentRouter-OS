# TASK-054: Offline Rust evaluation runner

Added a Rust runner for caller-supplied normalized evaluation cases. It runs the
Rust classifier, classification metrics and classification-only scorecard,
dataset-quality aggregation, and attaches explicit environment/dataset
metadata. This is a Partial port: adapter discovery, real dataset loading,
`measure_all` orchestration, and runtime provenance capture are not yet included.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_evaluation_runner_compat.py`:
  1 passed locally, comparing the Rust classifier report, grade, dataset-quality
  distribution, environment, and dataset metadata against Python.
- The differential caught and fixed grade rounding order. Evaluation-crate tests,
  formatting, and Clippy with warnings denied now pass.
- Adapter discovery, external dataset acquisition, `measure_all`, and runtime
  provenance remain partial.
- Cross-platform hosted checks follow the RC push.
