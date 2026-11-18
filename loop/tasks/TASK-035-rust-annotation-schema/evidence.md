# TASK-035 — Rust annotation artifact schema

## Contract covered

Added typed Rust artifacts for candidates, annotator labels, combined item
labels, adjudicated items, and dataset manifests. The implementation mirrors
Python defaults, rejects unknown fields, validates categories/sources/splits,
confidence bounds, abstention rules, and required labels, and exposes the
`ItemLabels.annotators`/`agrees` properties.

## Differential evidence

- Fourteen focused Rust/Python schema cases pass across all five model types,
  defaults, derived properties, invalid candidate/label/adjudication data, and
  datetime inputs (UTC and offset-aware, naive date/time, microseconds,
  fractional Unix seconds, numeric strings, null, and invalid values).
- `AnnotatorLabel.at` is normalized to Python-compatible ISO JSON form with
  microsecond precision. The module remains **Partial** because Pydantic's
  permissive scalar coercions and complete `datetime.fromisoformat` edge
  grammar have not yet been exhaustively matched.
- Local verification on 2026-11-11: `cargo test --workspace --locked`,
  `cargo clippy --workspace --all-targets --locked -- -D warnings`,
  `cargo fmt --all -- --check`, Ruff check/format, and the 14 focused
  compatibility cases pass. Full Python coverage is being refreshed.
