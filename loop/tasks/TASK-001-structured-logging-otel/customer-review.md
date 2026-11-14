# Customer review — TASK-001

Opt-in observability; default behavior unchanged (verification confirmed byte-identical
CLI stdout, zero stderr, by default).

- S1/S2 (first-time + everyday CLI): unaffected — no new default output, exit codes same.
- S3 (API integrator): X-Request-ID already echoed; now also in the structured log for
  end-to-end tracing. PASS.
- Discoverability/docs: README "Observability (opt-in)" section documents AGENTROUTER_LOG
  and AGENTROUTER_OTEL with the privacy guarantee. Env var names consistent with existing
  AGENTROUTER_HOME/AGENTROUTER_API_KEY. NO_COLOR unaffected (logs are JSON on stderr).
- Privacy: record carries task_len, never task text/prompt — matches Data & Privacy section.

Verdict: PASS. No confusing surface; a full customer-advocate pass was not warranted for
an opt-in env-var feature with no default-path change (ponytail).
