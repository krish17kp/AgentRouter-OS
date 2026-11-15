# TASK-152 — Rust route observability parity

## Goal

Emit the same privacy-safe route metadata from the Rust HTTP service that the
Python observability module provides, while keeping routine logs opt-in.

## Scope

- Move the existing Rust redaction and safe-echo helpers into a shared crate.
- Build route decision records without raw task or prompt text and propagate
  the HTTP request identifier into the route handler.
- Strictly redact credential-shaped values and nested keys at both Python and
  Rust logging boundaries; hash request IDs before writing them to logs.
- Compare the structured record with Python and exercise opt-in HTTP logging.

## Acceptance

- Rust and Python produce the same route-decision record for the declared
  classification, recommendation, gate, exclusion, and Unicode fixture.
- An opted-in Rust route request logs one correlated, redacted JSON record;
  disabling logging emits no route record.
- The route response and existing redaction behavior remain compatible.
- No release gate, dataset, or routing score changes.
