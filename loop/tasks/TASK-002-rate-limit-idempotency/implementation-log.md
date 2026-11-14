# Implementation log — TASK-002

## Files changed
- **NEW** `agentrouter/server/limits.py` — `RateLimiter` (fixed-window, opt-in via
  `AGENTROUTER_RATE_LIMIT`, disabled when <=0), `IdempotencyCache` (TTL via
  `AGENTROUTER_IDEMPOTENCY_TTL`), `client_key`, `CachedResponse`. Both stores bounded
  by `MAX_ENTRIES=10000` with oldest-first eviction (+expired purge).
- `agentrouter/server/app.py` — `limits_middleware`: rate-limit (probes exempt) -> 429 +
  Retry-After; POST + `Idempotency-Key` -> replay cached status+body (`Idempotency-Replay`
  header). Per-app store instances (test isolation).
- **NEW** `tests/test_server_limits.py` — 13 tests (unit + server integration).

## Decisions (ponytail)
- No new deps — pure stdlib (`threading`, `time`, `dataclasses`) over the existing FastAPI.
- Rate limiting DISABLED by default and idempotency only active with the header, so the
  default request path and all prior tests are unchanged.
- Fixed-window (not sliding) counter — simplest correct throttle; ceiling noted in module.
- Preemptively bounded both stores (MAX_ENTRIES) against a distinct-key memory-exhaustion
  DoS, with a `# ponytail:` comment naming the LRU upgrade path.

## Deviation from plan
- Added MAX_ENTRIES eviction (not in original plan) after recognising the unbounded-growth
  DoS ceiling — cheaper to bound now than to ship and patch.
