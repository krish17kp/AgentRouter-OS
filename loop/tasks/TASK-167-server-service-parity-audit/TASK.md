# TASK-167 — Server service full-module parity audit

Audit every public function and observable side effect in
`agentrouter.server.service` against `agentrouter-api::service`: home and registry
resolution, model/host listing, classification, routing, persistence, feedback,
dry-run behavior, malformed historical payloads, registry failures, arbitrary
integers, and no-execution safety. Promote only after exhaustive differential
evidence and independent review.

## Baseline

Existing tests compare list/classify/route, safety and preference paths,
persistence, feedback, dry-run, missing records, and unbounded context integers.
The module remains Partial pending a complete public-function, malformed-data,
error, and side-effect audit.

## Evidence and repairs

- Added `home()` with OS home resolution, no-argument `load_registry()`, and an
  explicit `load_registry_at()` internal path.
- Added direct-call `classify_task_args`/`route_task_args` facades, active
  metadata-only OpenTelemetry spans, and one correlated route log emitted from
  the service (the HTTP server passes request IDs without duplicate emission).
- Reproduced Python's unconditional registry load in dry-run; the attempted
  conditional divergence was reverted.
- Focused service/schema differential: 102 passed; full Rust workspace and
  strict Clippy passed; Ruff passed; full Python regression passed 2,728/7;
  independent audit cleared promotion.

## Decision

Promote `agentrouter/server/service.py` from Partial to Parity. The broader
`agentrouter/observability.py` API remains a separate Partial module.
