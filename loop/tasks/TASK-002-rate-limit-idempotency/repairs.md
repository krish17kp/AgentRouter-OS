# Repair loop — TASK-002 (iteration 1, all resolved)

From independent audit (security HIGH/MEDIUM + verification Bug A/B):

1. HIGH auth bypass + MEDIUM rate-key (root cause: features ran in outer middleware,
   trusting an unvalidated header before route auth)
   - fix: mirror auth in middleware; gate idempotency on `authed`; namespace cache key by
     identity; only trust API key as rate bucket when it validates (else host).
   - tests: test_idempotency_not_served_without_auth.
2. MEDIUM stale replay for different body
   - fix: include sha256(request body) in the cache key.
   - test: test_idempotency_body_change_not_replayed.
3. MEDIUM non-2xx cached
   - fix: only cache 200-299.
   - test: test_non_2xx_not_cached.
4. Bug A: replay dropped Content-Type (BaseHTTPMiddleware media_type is None)
   - fix: cache response.headers['content-type'] and set it on replay.
   - test: test_replay_preserves_content_type.
5. Bug B: 429 + replay lacked X-Request-ID (limits middleware was outermost)
   - fix: reorder so request_id_middleware is outermost (added last).
   - tests: test_request_id_present_on_replay, test_request_id_present_on_429.

Re-verify: `pytest -q` -> 399 passed; ruff clean; bandit 0. 1 iteration, no escalation.
LOW items (duplicate-header collapse, per-entry byte budget) documented as accepted ceilings.
