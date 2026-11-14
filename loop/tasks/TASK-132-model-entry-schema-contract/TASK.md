# TASK-132 — Direct ModelEntry schema contract parity

## Objective

Check the public Rust `ModelEntry` type directly against Pydantic for defaulted
and populated fields, scalar bounds, unknown/missing fields, nested execution
targets, serialization, and the `vendor`, `key`, `vendor_key`, and `name`
properties.

## Scope

- Add a direct Rust `ModelEntry` schema probe and normalize its resolved vendor
  value to Python's post-validation model dump.
- Enforce field-level finite/non-negative price constraints and the
  0–1 `ability_confidence` range during direct deserialization.
- Match Python's empty `display_name` fallback behavior in `ModelEntry::name`.
- Keep `agentrouter/schema.py` Partial until the public model and validator
  inventory is closed.
