# TASK-111 — Python-compatible annotation integer precision

## Objective

Remove the Rust annotation manifest's signed-64-bit ceiling. Python accepts
arbitrarily large integers in `DatasetManifest.schema_version` and its count
maps; Rust must preserve their exact values and emit them as JSON numbers.

## Contract cases

- Differentially cover 80-digit positive and negative JSON integers, integer
  strings, leading zeros, integral decimal strings, and existing boolean and
  float coercions.
- Keep all generated annotation YAML valid for Python and prevent serde_json's
  arbitrary-precision marker representation from leaking into YAML output.
- Keep generated provider catalog YAML valid after Cargo feature unification.
- Do not change evaluation thresholds, dataset labels, or frozen holdout data.

## Verification

Focused schema and annotation CLI differentials, provider catalog serialization,
full Python regression/coverage, Rust workspace tests, strict Clippy, formatting,
Ruff, and cross-platform hosted checks are recorded in `EVIDENCE.md`.

## Remaining scope

This task closes integer range parity only. Datetime grammar and any other
remaining annotation-schema differences keep the module marked Partial.
