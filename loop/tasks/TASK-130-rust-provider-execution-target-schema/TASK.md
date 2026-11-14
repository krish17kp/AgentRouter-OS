# TASK-130 — Direct Provider and ExecutionTarget schema parity

## Objective

Add a direct Python/Rust contract probe for the public `Provider` and
`ExecutionTarget` schema types, covering normalized defaults, bool coercion,
enum values, required fields, unknown fields, and invalid nested values.

## Scope

- Expose canonical Rust JSON serialization for `Provider` alongside its
  existing deserialization contract.
- Probe `Provider` and `ExecutionTarget` values independently of registry file
  loading, so their own serde defaults and validation are tested.
- Compare accepted and rejected values with the Python Pydantic models.

## Status limits

This closes direct roundtrip coverage for these two public schema types only.
`agentrouter/schema.py` remains Partial until all public models, enums,
validators, defaults, and derived properties are differentially covered.
