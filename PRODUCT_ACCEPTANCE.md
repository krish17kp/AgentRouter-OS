# Product Acceptance Evidence

## Current checkpoint — 2026-11-14

Product acceptance remains **not granted**. PR #16 is the sole open PR and has
no GitHub reviews. TASK-145 is pushed at `d80a6df`; build-smoke and readiness
report have passed, and other platform, Rust, Python, security, and mutation
checks are pending. The last critical mutation run had ten unreviewed OpenAI
status mutants; numeric thresholds passed, and direct status-boundary cases
are now in the selected suite locally. The last enforcing run was blocked by
context-band accuracy 0.6667 < 0.90; a new run is pending.

TASK-140 covers every Rust SDK endpoint across three API-key variants. TASK-141
adds injected transport, timeout and close parity, typed errors, malformed
fixture rejection, and deterministic unsupported-protocol handling. The 52-case
focused SDK/reliability selection, nine Rust SDK unit tests, full Rust workspace,
strict Clippy, format, Ruff, and the full Python suite pass locally. Full Python passes 2,550 tests
with 5 skips at 92.025% statement, 87.690% branch, and 91.030% combined
coverage; see `docs/COVERAGE_REPORT_2026-11-14-TASK-141.md`. TASK-144's local
OpenAI adapter differential rejects HTTP 300, 302, and 399 in both languages;
68 focused tests and three Rust adapter unit tests pass, with hosted validation
for TASK-144 running on `0d3ea70`. TASK-145 adds three full-output CLINC150
real-row differentials and is pushed at `d80a6df`; external dataset fetching
remains a documented Partial surface.
The Rust migration and product acceptance remain incomplete; no production
deployment or paid OpenAI request occurred.
The table below is historical.

## Historical assessment

_Current v0.5 release-candidate view, 2026-07-20. Historical per-task evidence is
retained under `loop/tasks/` and `loop/reports/`._

| Area | Implementation evidence | Verification state | Acceptance |
|---|---|---|---|
| Routing, controls, taxonomy, offline mode | Core `agentrouter` modules and CLI | Existing unit/integration suites; final full rerun pending | Provisionally pass |
| Safety and execution policy | Safety gates, argv execution, URL protections | Existing safety/injection suites; final security rerun pending | Provisionally pass |
| API and SDKs | FastAPI service, Python SDK, TypeScript SDK | Python baseline plus TS typecheck and 8/8 tests | Provisionally pass |
| MCP | Read/route/explain surface; no execute tool | Existing MCP suite; clean-wheel baseline | Provisionally pass |
| Observability and service controls | Structured logs, optional OTel, limits, idempotency | Existing focused suites | Provisionally pass |
| Plugin lifecycle | Ownership state, exclusive backup, transaction recovery, link/reparse rejection, exact restore, safe empty-dir cleanup | 48 focused tests; independent final security re-audit pending | Pending |
| Evaluation | All 100 points measured; immutable context comparator; frozen dev/holdout split | 98.32/100 and six non-context gates pass | **Fail: held-out context gate 0.5778 < 0.90** |
| Mutation quality | Bounded mutmut 3.6.0 Linux runner, thresholds, survivor allowlist, artifact upload | Harness tests pass; first real Linux run pending | Pending |
| Packaging and supply chain | Wheel/sdist, SBOM, provenance, upgrade guide | Takeover baseline passed; final clean-environment rerun pending | Pending |
| Release CI | Strict evaluation and mutation workflows | Release branch not pushed yet | Pending |

## Release decision

Product acceptance is **not granted**. A high overall evaluation grade does not
override the failed frozen held-out context gate, and no mutation threshold is
accepted without a real Linux score. External production prerequisites—live
provider access, paid-model measurements, hosted operations, beta feedback, and
owner publication decisions—also remain outside this local release candidate.
