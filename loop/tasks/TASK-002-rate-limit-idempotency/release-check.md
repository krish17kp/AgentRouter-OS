# Release check — TASK-002

| AC | Impl | Test | Verdict |
|----|------|------|---------|
| rate limit opt-in; 429+Retry-After | limits.RateLimiter + app.limits_middleware | test_rate_limit_* | PASS |
| idempotent replay, no 2nd decision | app.limits_middleware + IdempotencyCache | test_idempotent_post_replays_same_decision (DB-verified) | PASS |
| default unchanged; no new deps | disabled-by-default; stdlib only | full suite 399 passed | PASS |
| stores bounded | MAX_ENTRIES eviction | test_*_bounded (50k-key verified) | PASS |
| docs | README "Server limits (opt-in)" | — | PASS |

Security gates: HIGH auth-bypass + 3 MEDIUM all fixed with regression tests; bandit 0.
No CRITICAL/HIGH remaining. Policy-enforcement paths (rate limit, auth-gated cache) tested.

**Verdict: PASS** for TASK-002 (not a product release; repo remains BLOCKED_EXTERNAL).
Accepted LOW ceilings: duplicate-header collapse (no cookies emitted), per-entry byte budget.
