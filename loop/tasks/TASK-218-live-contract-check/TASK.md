# TASK-218 — Live OpenAPI contract check

## Objective

Allow the Rust unified CLI to compare the committed OpenAPI baseline with a
running service without weakening the existing compatibility gate.

## Acceptance

- `agentrouter contract check --live URL` fetches the document with bounded,
  redirect-free, credential-free transport;
- an explicit `--baseline PATH` can be used for CI/base-branch comparisons;
- response size, JSON shape, local references, and schema surface are checked;
- drift returns a non-zero status and JSON output includes the compatibility
  report;
- local HTTP tests cover a valid response and redirect refusal;
- no claim is made that this replaces Python framework generation or hosted
  release approval.
