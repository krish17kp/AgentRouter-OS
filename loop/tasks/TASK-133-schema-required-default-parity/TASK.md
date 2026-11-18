# TASK-133 — Complete public schema required/default contract coverage

## Objective

Close direct Python/Rust parity coverage for the public `agentrouter.schema`
models by checking every required field and omitted optional defaults, with
focus on `Classification` and the remaining required fields across the schema
types.

## Scope

- Verify Pydantic and Rust both reject omission of each required field in
  `Ability`, `ExecutionTarget`, `Provider`, `ModelEntry`, and `Classification`.
- Verify omitted Classification defaults and its populated optional fields
  normalize identically, including the optional alternative task enum.
- Extend finite confidence rejection to positive and negative infinity.
- Mark `agentrouter/schema.py` as parity-complete only after focused and full
  regression checks pass and every public model, enum, validator, and derived
  property has direct evidence.
