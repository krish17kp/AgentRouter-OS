# TASK-145 — CLINC150 raw-row normalization contract

## Objective

Give the existing Rust CLINC150 normalizer direct, full-output differential
coverage against Python's real-row adapter behavior.

## Scope

- Compare every normalized `EvaluationCase` field for all curated CLINC intent
  hints, unknown intents, and the out-of-scope class.
- Cover ordered substring matching, duplicate suppression, source-row IDs,
  Unicode task text, and normalized-hash deduplication.
- Keep external Hugging Face fetching outside Rust and keep the module marked
  Partial while Python's optional `datasets` loader contract remains unmatched.

## Acceptance

- Rust output equals Python `model_dump(mode="json")` for the selected offline
  real-row fixtures.
- No external network access is used.
- The parity matrix does not overstate full adapter parity.
