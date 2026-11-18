# Implementation log — TASK-001

## Files changed
- **NEW** `agentrouter/observability.py` — stdlib-only route logging + opt-in OTel:
  `route_decision_record`, `log_route_decision`, `route_span`, `set/get_request_id`,
  `otel_enabled`, `configure_logging`.
- `agentrouter/cli.py` — import observability + uuid; in `route`: `configure_logging()`,
  per-invocation `request_id`, `set_request_id`, wrap `engine_route` in `route_span`,
  `log_route_decision` after decision persisted.
- `agentrouter/server/service.py` — import observability; wrap `engine_route` in
  `route_span`; `log_route_decision` at end of `route_task`.
- `agentrouter/server/app.py` — middleware calls `set_request_id(rid)` so the service
  log carries the X-Request-ID.
- `pyproject.toml` — added optional `[otel]` extra (opentelemetry-api/sdk).
- **NEW** `tests/test_observability.py` — 9 tests.

## Decisions (ponytail)
- Reused the existing X-Request-ID middleware; propagated via a ContextVar instead of
  changing function signatures. No new deps in the core path.
- Structured logs are silent by default (INFO, no handler) so existing CLI output and
  the 371 prior tests are unchanged; visibility is opt-in via `AGENTROUTER_LOG`.
- Privacy: record carries `task_len` (int), never the task string or generated prompt.
- OTel is a guarded optional import; `route_span` is a zero-cost no-op unless
  `AGENTROUTER_OTEL` truthy AND opentelemetry importable.

## No deviations from plan.
