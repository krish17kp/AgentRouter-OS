# Production Readiness — AgentRouter OS

_Last assessed: 2026-07-20._

## Verdict: NOT READY

The product has a broad local implementation and a 98.32/100 measured evaluator,
but production readiness cannot be claimed while the canonical held-out context
gate fails, mutation thresholds lack a real Linux result, and the release branch
has not passed its full GitHub matrix.

## Locally implemented

- Core routing, controls, safety policy, tool taxonomy, CLI, setup, and offline mode.
- FastAPI service and Python SDK, MCP read/route surface, and TypeScript SDK.
- Structured logging/optional tracing, rate limits, and idempotency controls.
- Reversible plugin installer with ownership state, crash journal, exact backup
  restoration, link/reparse defenses, and empty-directory identity checks.
- Full 100-point evaluator plus frozen development/holdout context datasets.
- SBOM/provenance release wiring, property tests, and a bounded Linux mutation job.

## Current blockers

1. Frozen context holdout accuracy is 0.5778, below 0.90.
2. Real Linux mutation scores and survivor review are pending.
3. Final local verification and release-branch GitHub checks are pending.
4. Live catalogs/access, paid-model profiles, hosted infrastructure, beta feedback,
   incident/rollback exercises, and owner security sign-off remain external.
