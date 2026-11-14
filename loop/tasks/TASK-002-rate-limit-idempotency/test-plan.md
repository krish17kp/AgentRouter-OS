# Test-first contract — TASK-002

Unit:
- RateLimiter disabled by default (limit<=0 -> always allowed).
- fixed-window: exactly `limit` pass, next is 429 w/ retry>=1, window rollover resets.
- keys independent; client_key prefers API key else host else 'unknown'.
- IdempotencyCache TTL expiry; both stores bounded by MAX_ENTRIES (oldest-first).

Server integration:
- rate limit disabled -> all through; enabled -> 429 + Retry-After + structured error code.
- /health exempt even at limit=1.
- POST + Idempotency-Key: 2nd call replays (Idempotency-Replay true) AND same decision_id
  (no second decision persisted).
- different key -> distinct decisions; no key -> distinct decisions, no replay marker.

Security/DoS:
- bounded stores; bandit clean.

Regression: full `pytest -q` >= 391 (now 393).
