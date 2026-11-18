# TASK-182 — Reliability response consumption

## Contract

The Rust reliability harness must consume each HTTP response body before
recording success, matching Python/httpx behavior for truncated responses.

## Scope

- drain successful and non-successful response bodies;
- classify body-read timeout/error as transport failure;
- preserve status, request-id, and latency reporting for complete responses;
- keep timing indicative-only and do not introduce a latency gate.
