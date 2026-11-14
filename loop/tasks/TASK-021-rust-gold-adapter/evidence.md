# TASK-021 — Rust AgentRouter gold adapter parity

## Contract covered

Ported the Python AgentRouter gold adapter surface: metadata, availability,
description, loading, deterministic sampling, and aggregate checksum. The Rust
loader derives approval labels from the accepted risk set, retains the human
provenance and approved review status, fills the dataset version and source,
and applies the normalized task checksum. Python remains the canonical source
of labels and release evaluation.

## Differential evidence

- `tests/test_rust_agentrouter_gold_compat.py` compares Python and Rust JSON for
  all 165 records in `classifier_gold_v1.yaml`, including metadata, description,
  status, checksum, seeded sampling, no-limit sampling, and zero-result sampling.
- A second fixture compares Unicode punctuation, omitted labels/defaults,
  unknown row metadata, risk-derived approvals, and version override behavior.
- Missing-file, malformed-document, duplicate-ID, and duplicate-task errors
  are compared against Python's adapter error category and message.
- Focused evaluation compatibility tests: 31 passed.
- Rust workspace tests: passed.
- Rust Clippy (`-D warnings`): passed.
- `cargo fmt --all -- --check`: passed.
- Ruff check and format: passed.
- Full Python suite on the cumulative RC worktree: 1,757 passed, 6 skipped;
  91.24% line, 85.80% branch, 90.00% combined coverage (Python 3.12.15, Linux).
- Cross-platform PR CI on RC `a7e5cf3`: Linux, Windows, macOS, Rust 1.89,
  Python/Rust compatibility, security, and mutation checks passed. PR #16's
  promotion gate remains the only failure because the frozen context-band score
  is 0.6667 < 0.90; live smoke is skipped without credentials.

## Scope limits

This ports one dataset adapter module. The shared adapter base, external dataset
adapters and downloads, evaluation runner/CLI, context-band release gate, and
annotation workflow are still not Rust-parity complete. See
`docs/RUST_PARITY_MATRIX.md`.
