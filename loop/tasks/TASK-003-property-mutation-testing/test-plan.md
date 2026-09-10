# Test-first contract — TASK-003

Property tests (Hypothesis, marked `property`, importorskip-guarded):
- classify: output invariants over st.text; risk-override wins over st.sampled_from(Level);
  determinism (same input -> same model_dump).
- RateLimiter: over random (limit, n), allowed == min(n, limit).
- IdempotencyCache: over random (key, body), put->get returns same body within TTL.
- observability: over random task text, sentinel-prefixed task never appears in the record;
  task_len exact.

Regression: full `pytest -q` stays green (405).
Coverage: `pytest --cov=agentrouter.server.limits` -> 95.16%.

Mutation: BLOCKED (env) — see implementation-log / KNOWN_LIMITATIONS.
