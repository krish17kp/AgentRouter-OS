# Product Master Plan

Canonical phase roadmap lives in `command.md` (§5, P0–P14) and `ROADMAP.md`. This file
tracks execution status per phase; it does not restate the specs.

| Phase | Title | Status | Notes |
|-------|-------|--------|-------|
| P0 | Repository truth & baseline | observed | 276 tests green at start SHA 476c51a; no placeholder production seed IDs; offline route works. Full `artifacts/production-baseline/` bundle not regenerated this loop. |
| P1 | Real model catalogs (refresh) | blocked_external | `models list/show` done; `providers refresh` legacy path works; new-schema live refresh needs authenticated APIs. |
| P2 | Host discovery & access verification | partial | `hosts list/doctor/show` done (PATH + env presence); live `hosts verify` needs opt-in network. |
| **P3** | **Routing controls, confidence, abstention** | **done** | Route-control flags + confidence/abstention both shipped, tested, documented. `--privacy local-only`/`--max-estimated-cost` deferred (see KNOWN_LIMITATIONS). |
| P4 | Tool/workload taxonomy | done | `taxonomy.py` versioned canonical labels + equivalence; alias-aware eligibility (backward-compatible); `--prohibit-tool`; seed-label hygiene test. *Optional*-tool modeling deferred. |
| P5 | Measured model profiles | blocked_external | needs benchmark/inference runs. |
| P6 | 100-point evaluation system | done (local) | All 6 remaining evaluators implemented (`eval run --all`); `grade(measure_all)`; additive gates. Grade 96.89/100 on fixtures, 2 gates FAIL honestly → not rescaled. Hypothesis/mutmut/promptfoo/DVC/MLflow extras still optional/unwired. |
| P7 | Production API & SDK | partial | Local FastAPI service (9 `/v1` endpoints, OpenAPI, request-id, optional API-key, **no remote exec**) + Python SDK + `agentrouter server`. TypeScript SDK, rate-limit enforcement, PostgreSQL path pending. |
| P8 | Plugin & skill ecosystem | partial | **Installer DONE** (`plugin list/install/uninstall/doctor`, reversible/idempotent, wheel-packaged, Windows-tested). MCP server, `/route*` commands, examples/, Linux-CI install still pending. |
| P9 | CLI & UX (`setup` wizard) | partial | **`setup` wizard DONE** (non-interactive, idempotent, secret-safe). Richer `--details`/`--quiet`/shell-completion output polish still pending. |
| P10 | Observability, security, governance | partial | **Security scanning DONE** (bandit 0 issues, pip-audit clean, secret scan, URL-scheme hardening, security CI). Structured logging/OpenTelemetry/metrics pending. |
| P12 | Distribution & adoption | partial | `examples/README.md` (verified commands) added; README quickstart + full docs polish pending. |
| P11/P13/P14 | Hosted, beta/prod gates | not_started / blocked | P11 needs owner infra; P13/P14 gated on P6 evaluators + real beta. |

**Prioritization (command.md §7):** finish fully-local trust-critical work first.
Route controls (P3) shipped; next local slice = P3 confidence/abstention, then P4 taxonomy.
Catalog/host-verify/measured-profiles are external-blocked until credentials/APIs.
