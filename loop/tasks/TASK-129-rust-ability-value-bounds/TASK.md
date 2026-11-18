# TASK-129 — Direct Rust Ability contract bounds

## Objective

Make the Rust `Ability` value enforce the same Pydantic `0 <= score <= 10`
integer constraints when deserialized directly as Python does, rather than
relying on the containing `ModelEntry` registry validation.

## Verification

Python/Rust differential cases exercise accepted coercions, all field bounds,
unknown fields, and missing required fields. Record focused and workspace test
results in `EVIDENCE.md`.

## Status limits

This closes direct `Ability` deserialization parity only. The complete
`agentrouter/schema.py` public module remains Partial until every public model,
enum, default, validator, and derived property has a module-level differential
contract.
