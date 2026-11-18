# TASK-030 — Rust evaluation provenance parity

## Contract covered

Completed the Rust mirror of `evaluation.provenance`: dataset-quality/leakage
aggregation and the four-field environment snapshot (`agentrouter_version`,
`python`, `platform`, and nullable `git_sha`). Runtime-derived values are
passed into Rust so the computation remains deterministic and does not make
false claims about the Rust process environment.

## Differential evidence

- Existing dataset-quality differential cases cover duplicate tasks, leaked
  paraphrase families, language/domain/risk/task distributions, and provenance.
- Added a Python/Rust exact contract check for environment snapshots.
- Focused provenance and TwinRouterBench tests, Rust workspace tests/Clippy/
  format, Ruff, and diff checks pass locally.
- Full suite and cross-platform CI are recorded after the current run completes.
