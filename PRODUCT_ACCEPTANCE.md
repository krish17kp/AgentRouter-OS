# Product Acceptance Evidence

## Current checkpoint — 2026-11-14

Product acceptance remains **not granted**. PR #16 is the sole open PR. The
local TASK-114/115 candidate passes the Rust workspace, strict Clippy, and the
full mutation campaign (0.9698 overall, zero unreviewed survivors). The full
pytest 9.0.3 regression passes 2,262 tests and 4 skips at 91.96% statement,
87.65% branch, and 90.97% combined coverage. TASK-114 adds journaled
managed-plugin upgrades and fixes the
failures observed at pushed head `b244ad1`; hosted Linux/Windows/macOS
validation remains pending.
`pip-audit` found the vulnerable development-only pytest 8.4.2 pin; pytest
9.0.3 is now required and the audit is clean.
The frozen context-band gate remains 0.6667 < 0.90. Rust R4 and R5–R13 remain
incomplete; no production deployment or paid OpenAI request occurred.
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
