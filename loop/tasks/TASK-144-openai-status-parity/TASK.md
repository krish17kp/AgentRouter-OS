# TASK-144 — OpenAI non-2xx status parity

## Objective

Ensure both OpenAI Responses adapters reject every non-2xx response even when
the status comes from an injected transport fixture.

## Scope

- Reject 3xx as well as 4xx/5xx in Python and Rust adapter response handling.
- Preserve the existing no-redirect HTTPS behavior and safe HTTP status error.
- Add offline Python/Rust status cases for 300, 302, and 399.

## Acceptance

- All non-2xx adapter responses fail with matching HTTP status diagnostics.
- Existing OpenAI adapter, execution-gate, and redirect tests remain green.
- No live provider call or credential is required.
