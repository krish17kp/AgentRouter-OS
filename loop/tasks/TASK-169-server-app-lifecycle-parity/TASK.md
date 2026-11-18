# TASK-169 — HTTP application lifecycle parity audit

Audit `agentrouter.server.app` against `agentrouter-api::server` after the
service and observability slices are complete. Cover middleware ordering,
request-ID response guarantees, authentication and CORS policy, rate limits,
idempotency replay, typed validation/registry/internal errors, panic-safe
responses, readiness, docs, and safe error messages. Promote only with direct
Python/Rust process differentials and fail-closed security checks.

## Baseline

Rust already serves the documented local routes, request schemas, service
operations, request IDs, auth, CORS allowlists, rate limiting, idempotency,
typed error envelopes, and OpenAPI contract. The matrix remains Partial because
the FastAPI lifecycle and middleware edge cases have not yet been audited as a
complete module, especially short-circuit request-ID behavior, replay headers,
exception paths, and preflight/error responses.
