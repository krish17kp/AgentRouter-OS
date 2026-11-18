# Customer review — TASK-002

Opt-in server hardening; default behavior unchanged (rate limit off unless configured;
idempotency only with the header).

- S3 (API integrator): retries are now safe (Idempotency-Key -> no duplicate decision);
  429 carries Retry-After + X-Request-ID; structured error code `rate_limited`. PASS.
- Discoverability/docs: README "Server limits (opt-in)" documents all three env vars,
  the Idempotency-Key contract, and the single-process/in-memory caveat. Names consistent
  with existing AGENTROUTER_* vars. PASS.
- Probes: /health and /ready exempt from throttling -> orchestrators won't get 429. PASS.

Verdict: PASS.
