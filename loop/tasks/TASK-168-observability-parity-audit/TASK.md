# TASK-168 — Observability full-module parity audit

Audit `agentrouter.observability` against `agentrouter-observability`: request
context propagation, opt-in logging, route records, redaction, structured event
and API-error logging, OpenTelemetry opt-in spans, safe echoes, and silent
defaults. Keep raw tasks, prompts, credentials, and request IDs out of emitted
records. Promote only after direct differential evidence and an independent
security review.

## Baseline

Rust already covers recursive redaction, safe echoes, hashed request IDs, route
record construction, and opt-in route emission. The Python module additionally
exports context-id, logging configuration, generic event/error logging, and
OpenTelemetry-enabled helpers; these remained unported and kept the matrix row
Partial.

## Error-evidence note

Rust exposes the same bounded structured error shape and strict redaction
boundary. The HTTP service does not retain a Python traceback object across its
`spawn_blocking` boundary, so service errors intentionally emit a bounded,
redacted message-only record; direct callers may provide an already-rendered
traceback to `log_api_error`, which is redacted before emission. Generic
internal responses are logged once at construction, while detailed service
errors are logged at the conversion boundary to avoid duplicate records.
