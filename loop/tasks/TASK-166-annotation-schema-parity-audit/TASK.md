# TASK-166 — Annotation schema full-module parity audit

Audit every public constant, model field, required/default contract, scalar and
datetime coercion, cross-field validator, derived property, serialization rule,
and unknown-field policy in `agentrouter.annotation.schema` against
`agentrouter-evaluation::annotation_schema`. Promote only after exhaustive
differential evidence and independent review.

## Baseline

The existing Rust implementation and differential suite cover all five models,
core cross-field validation, arbitrary-precision manifest integers, boolean and
float coercion, datetime normalization, `annotators`, and `agrees`. The parity
matrix keeps the module Partial because the earlier evidence explicitly left
broader datetime grammar and the complete public/default/rejection inventory
unfinished.

## Audit repair

Independent review found that four public Rust types could deserialize without
running their semantic validators. Each now deserializes through a private
unchecked DTO and `TryFrom`, making validation inseparable from construction and
transitive through nested labels. The expanded datetime boundary suite also
found a positive half-microsecond rounding mismatch; Rust now matches Pydantic.

## Evidence

- Direct Python/Rust schema differential: 77 passed.
- Annotation schema/store/packs/compare/splits/CLI production paths: 108 passed.
- Evaluation crate tests and strict Clippy: passed.
- Full Rust workspace tests and strict workspace Clippy: passed.
- Full Python regression: 2,719 passed, 7 skipped in 450.56 seconds.
- Public constants, minimal defaults, every required missing/null field,
  top-level and nested forbidden extras, agreement/disagreement/abstention, and
  expanded datetime boundaries are covered.
- Independent re-review explicitly cleared promotion after the repairs.

## Decision

Promote `agentrouter/annotation/schema.py` from Partial to Parity. Annotation CLI
orchestration remains a separate Partial row.
