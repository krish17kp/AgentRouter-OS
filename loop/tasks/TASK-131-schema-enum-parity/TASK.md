# TASK-131 — Direct Python/Rust parity for schema enums

## Objective

Differentially verify every public enum in `agentrouter/schema.py` against its
Rust enum, including every accepted string value and representative invalid
types/values.

## Scope

- Extend the direct Rust schema-value probe to all twelve public enums.
- Use Pydantic `TypeAdapter` as the reference for accepted values and errors.
- Preserve Python's enum string values exactly, including values with `+` and
  hyphens.
- Keep `agentrouter/schema.py` Partial until all public models, coercions,
  validators, defaults, and derived properties are covered.

## Status

All 45 enum variants and 36 invalid value/type cases match Pydantic in direct
Python/Rust probes. The complete Python regression and Rust workspace pass
locally; hosted checks are pending the RC push.
