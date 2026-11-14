# TASK-149 — Differential JSON redaction coverage

## Goal

Protect the nested JSON redaction boundary shared by Python observability and
the Rust diagnostics/CLI helpers.

## Scope

- Expose the existing Rust `redact_value` helper through the compatibility probe.
- Compare nested objects, arrays, path-shaped diagnostics, and credential-shaped
  values against `agentrouter.observability.redact_value`.
- Keep the observability module Partial: structured logs, request context,
  tracing spans, API error records, and OTel are outside this slice.

## Acceptance

- The Rust helper returns the same JSON value as Python for the declared nested
  fixtures.
- Secrets are removed while ordinary diagnostic paths remain intact.
- No release thresholds or evaluation data change.
- Linux, Windows, and macOS checks pass after the RC push.
