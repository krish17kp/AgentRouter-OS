# AgentRouter OS v0.5.0 release candidate 1

**Status: candidate only; not approved for release or deployment.** The frozen
context-band evaluation remains below its existing release threshold, and the
required independent human annotation and adjudication round is incomplete.

## Included

- Hardened local REST API request limits, privacy, and observability.
- Rust migration slices for registry validation, routing, policy, hosts,
  decision storage, provider status, dashboard reporting, harness detection,
  observability helpers, context-band inference, and structured diagnostics with
  an allowlisted diagnostic bundle and opt-in SQLite snapshot; plus a paired
  release-mode Rust routing benchmark with documented synthetic-workload limits.
- Rust/OpenAI Responses transport support behind the existing opt-in and safety
  gates; live provider validation has not been run.
- Cross-platform Rust and Python compatibility coverage and measured local
  routing latency and Python coverage reports.
- Website interface and product-truth updates.
- Diagnostic bundle settings show presence only; configured values such as user identifiers and log paths are withheld in both Python and Rust.
- Rust `route_cli --verify-live` mirrors Python's one-step rerank when a live quota check confirms the top model is exhausted; no live quota adapter is enabled by default.
- Rust doctor `--verify-live` now uses the shared host detector and bounded usage state machine; it checks only authenticated hosts and reports `unsupported` until a provider adapter exists.

## Release gates still open

- Context-band accuracy is 0.6667 on the frozen 45-case set against the
  unchanged 0.90 threshold. Do not alter labels, use AI to annotate/adjudicate,
  tune against the frozen holdout, or lower the threshold.
- Rust migration is partial. Python remains the shipping implementation; the
  Rust probes are not a drop-in replacement for the complete CLI, HTTP/MCP,
  plugin/skill, evaluation, or annotation surfaces.
- OpenAI live validation needs an owner-supplied key and authorization for one
  bounded paid smoke test.
- Production release/deployment needs owner credentials and infrastructure.

See [PRODUCTION_STATUS.md](../PRODUCTION_STATUS.md) and
[RELEASE_READINESS.md](../RELEASE_READINESS.md) for current gate evidence.
