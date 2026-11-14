# Independent audit — TASK-002

## verification-engineer — ALL 4 ACs PASS
- 393->399 tests pass, no skips. Fixed-window boundary exact (limit pass, limit+1 -> 429);
  race-free under 32 threads (500 req/limit=50 -> exactly 50x200, 450x429).
- Idempotency proven at DB level: repeated POST => only ONE decision row persisted.
- No cross-path collision (key includes method+path). Stores bounded at 10k under 50k keys.
- Found 2 real bugs (fixed in repair loop): (A) replay dropped Content-Type;
  (B) 429 + replay lacked X-Request-ID.

## security-reviewer-arros — bandit 0; 1 HIGH + 3 MEDIUM (all fixed)
- HIGH: idempotency replay ran before route auth -> unauthenticated caller could replay a
  cached authenticated response. FIXED: cache gated on `authed`, key namespaced by identity.
- MEDIUM: body not in key -> stale replay for a different payload. FIXED: sha256(body) in key.
- MEDIUM: non-2xx cached (transient 503/401 pinned). FIXED: only cache 2xx.
- MEDIUM: rate-key trusted unvalidated X-API-Key (rotatable -> unlimited buckets).
  FIXED: only trust the key when it validates, else bucket by host.
- LOW: dict(headers) collapses duplicate headers -> latent (no cookies today), documented.
- LOW: no per-entry byte budget -> entry-count bounded; bodies are server-generated JSON. Documented.
