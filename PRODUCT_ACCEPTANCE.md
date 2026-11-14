# Product Acceptance Evidence

## Current checkpoint — 2026-11-14

Product acceptance remains **not granted**. PR #16 is the sole open PR. At
pushed head `52c9565`, Rust workspace passes on Linux, Windows, and macOS;
Python 3.10–3.13, macOS full-suite, Linux/macOS Python/Rust compatibility,
site, scan, build smoke, release report, and critical-module mutation checks
pass. Windows Python/Rust compatibility and full-suite jobs failed because a
closed ephemeral port was filtered as a timeout; a reserved port-zero fixture
passes locally and awaits hosted revalidation. The enforce-release-gate remains blocked by context-band accuracy
0.6667 < 0.90; live smoke skips without an OpenAI credential.

TASK-140's local SDK differential covers every Rust SDK endpoint and passes
three API-key variants; the full Rust workspace, strict Clippy, format, Ruff,
and 29 focused Python SDK tests pass. Full Python passes 2,538 tests with 5
skips at 92.025% statement, 87.690% branch, and 91.030% combined coverage.
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
