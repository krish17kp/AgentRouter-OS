# TASK-208 — Rust contract CLI surface

## Objective

Expose the already differential-tested Rust OpenAPI baseline and surface
comparison helpers through the unified command without presenting them as a
replacement for the live Python compatibility gate.

## Acceptance

- `agentrouter contract check --json` validates the committed baseline and
  reports its intentionally non-live scope;
- `agentrouter contract diff PATH [--json]` reports compatible additive/risky
  changes and returns a failing exit code for breaking surface changes;
- malformed or untrusted baselines still fail closed through the existing
  reference and size guards;
- focused unified CLI tests, formatting, workspace checks, and strict Clippy
  pass;
- documentation keeps the Python live-schema gate authoritative.
