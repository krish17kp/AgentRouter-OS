# Production Readiness — AgentRouter OS

_Last assessed: 2026-11-17._

## Verdict: NOT READY

The product has a broad local implementation and a 98.23/100 measured evaluator,
but production readiness cannot be claimed while the canonical held-out context
gate fails and owner-controlled validation, promotion, and deployment inputs
remain incomplete.

## Locally implemented

- Core routing, controls, safety policy, tool taxonomy, CLI, setup, and offline mode.
- FastAPI service and Python SDK, MCP read/route surface, and TypeScript SDK.
- Structured logging/optional tracing, rate limits, and idempotency controls.
- Reversible plugin installer with ownership state, crash journal, exact backup
  restoration, link/reparse defenses, and empty-directory identity checks.
- Full 100-point evaluator plus frozen development/holdout context datasets.
- SBOM/provenance release wiring, property tests, and a bounded Linux mutation job.

## Current blockers

1. Frozen context holdout accuracy is 0.6667, below the unchanged 0.90 threshold.
2. The Rust migration has 60/77 contract-parity rows; 17 remain Partial.
3. PR #16's enforcing release gate fails honestly; required human review is absent.
4. Live catalogs/access, paid-model profiles, hosted infrastructure, beta feedback,
   incident/rollback exercises, and owner security sign-off remain external.
