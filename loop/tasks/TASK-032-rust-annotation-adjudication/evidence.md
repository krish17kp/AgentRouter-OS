# TASK-032 — Rust human annotation adjudication

## Contract covered

Ported `annotation.adjudicate.resolve` into the Rust evaluation crate. It
preserves the Python rules for unanimous labels, unanimous abstention,
unresolved disagreement, mixed abstention, and explicit adjudicator decisions.
The Rust function only folds human-supplied labels; it does not generate or
infer labels.

## Differential evidence

- Python/Rust exact output comparisons cover agreement, unanimous abstention,
  unresolved disagreement, explicit band decisions, mixed abstention, explicit
  adjudicator abstention, and missing labels.
- The differential suite is required in Rust migration CI on Linux, Windows,
  and macOS.
- Focused differential, Rust workspace, Clippy, format, Ruff, and diff checks
  pass before commit; complete regression and hosted CI are recorded after push.
- The human annotation round and release gate remain open until independent
  annotators and a human adjudicator supply the required blinded dataset.
