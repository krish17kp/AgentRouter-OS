# Test-first contract — TASK-001

Positive:
- record has event/request_id/decision_id/task_type/risk/recommended_model/excluded_count/task_len.
- log_route_decision emits exactly one JSON line on logger `agentrouter.route`.
- request-id ContextVar used when request_id not passed.
- server /v1/route log record's request_id == X-Request-ID header.

Negative / boundary:
- recommendation None -> valid record, key dropped, no crash.
- None fields dropped from record.

Security / privacy:
- raw task text and prompt NEVER present in the record JSON.

OTel opt-in:
- route_span yields None when AGENTROUTER_OTEL unset.
- route_span yields None when opted-in but opentelemetry missing.

Config:
- configure_logging False unless AGENTROUTER_LOG truthy; idempotent (one handler).

Regression:
- full `pytest -q` stays >= 371 (now 380).
