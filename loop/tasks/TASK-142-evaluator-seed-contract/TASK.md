# TASK-142 — evaluator seed catalog full contract

## Objective

Strengthen the Rust evaluator facade compatibility contract so its embedded
seed catalog is compared field-for-field with Python and its exports follow the
actual Python package declaration.

## Scope

- Serialize complete Rust `ModelEntry` values from the evaluator facade probe.
- Normalize Rust's optional vendor storage through the public `vendor()` value,
  matching Python's dependent default.
- Compare every packaged seed model to `model_dump(mode="json")`.
- Compare Rust facade exports directly to Python's `evaluators.__all__`.
- Keep the evaluator module Partial until Rust evaluator runtime discovery and
  orchestration match the Python package.

## Acceptance

- The focused Python/Rust evaluator facade differential passes.
- The Rust probe contains no hand-maintained list of model fields or exports.
- The parity matrix documents the remaining runtime orchestration gap honestly.
