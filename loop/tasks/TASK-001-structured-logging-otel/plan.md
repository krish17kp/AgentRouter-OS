# Plan — TASK-001 structured logging + opt-in OpenTelemetry

## Discovery (evidence)
- Route decisions funnel through `engine.route(models, cls, ...)`, called by:
  - `agentrouter/cli.py:417` (CLI `route` command) — builds `payload`, saves at :443.
  - `agentrouter/server/service.py:126` (`route_task`) — builds identical `payload`, saves at :148.
- Request-id already exists server-side: `server/app.py:59-64` middleware sets
  `X-Request-ID` on the response. No logging anywhere except that middleware.
- `payload["classification"]` = `Classification.model_dump()` → `task_type`, `risk`, `confidence`.
- `payload["recommendation"]` (a scored row, `engine.py:157`) → `model`, `provider`,
  `pricing_tier`, `score`. `payload["gates"]["auto_execute_allowed"]`.

## Design (minimal)
New module `agentrouter/observability.py` (stdlib-only core):
- `log_route_decision(*, task, payload, decision_id, request_id)` → emits ONE JSON
  record on logger `agentrouter.route` via `logger.info(json.dumps(...))`.
  **Privacy:** logs `task_len` (int), never raw task text or the generated prompt.
- `set_request_id`/`get_request_id` via a `ContextVar` so the server middleware can
  propagate the request id into `service.route_task` without changing signatures.
- `route_span(name, **attrs)` context manager: no-op unless `AGENTROUTER_OTEL` is
  truthy AND `opentelemetry` importable → then a real span. Never a hard dependency.
- `configure_logging()`: opt-in (`AGENTROUTER_LOG` truthy) StreamHandler so records
  are visible; default stays silent (no new CLI/stderr output → existing tests unaffected).

## Wiring
- `cli.py`: generate a per-invocation request id, wrap routing in `route_span`,
  call `log_route_decision`. Call `configure_logging()` once at CLI entry.
- `service.route_task`: wrap in `route_span`, call `log_route_decision`.
- `server/app.py` middleware: `set_request_id(rid)` so the service log carries it.

## Compatibility / risk (low)
- Additive only. No signature changes to public functions. Default output unchanged
  (INFO with no handler is silent → 371 existing tests must stay green).
- opentelemetry stays an OPTIONAL extra (`pip install agentrouter-os[otel]`); absent → no-op.

## Tests (test-first)
- record contains request_id/decision_id/task_type/risk/recommended_model; NO task text.
- `no_log` / missing recommendation still emits a valid record.
- `route_span` is a no-op (yields None) when env unset or otel missing.
- request-id contextvar round-trips; server route log carries the header id.
- regression: full `pytest -q` stays 371+.
