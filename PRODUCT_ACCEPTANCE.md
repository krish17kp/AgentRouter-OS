# Product Acceptance Evidence

## Current checkpoint — 2026-11-15

Product acceptance remains **not granted**. At `5af3c55`, the Python, Rust,
cross-platform compatibility, API, build, security, website, and mutation jobs
pass. The frozen context-band evaluation gate remains 0.6667 < 0.90; PR #16
has no human review, and live OpenAI smoke still needs credentials. TASK-152
adds opt-in, redacted route records to the Rust HTTP service. Full local Python
regression passes 2,590/5 and Rust workspace/Clippy pass; hosted validation
awaits the RC push. The 77-module Rust inventory has
48 Parity and 29 Partial rows.

## Previous checkpoint — 2026-11-14

Product acceptance remains **not granted**. PR #16 is the sole open PR and has
no GitHub reviews. On pushed head `0d0a662`, Python, Rust, Windows/macOS,
compatibility, API, build, security, and site checks pass. The critical mutation
gate fails on one unreviewed missing-status mutant; the enforcing gate fails at
context-band accuracy 0.6667 < 0.90. TASK-146's local repair now rejects
missing/malformed statuses and kills that exact mutant. TASK-147 locally bounds
Rust SDK TCP connection setup by the configured timeout.

TASK-140 covers every Rust SDK endpoint across three API-key variants. TASK-141
adds injected transport, timeout and close parity, typed errors, malformed
fixture rejection, and deterministic unsupported-protocol handling. The 52-case
focused SDK/reliability selection, ten Rust SDK unit tests, full Rust workspace,
strict Clippy, format, Ruff, and the full Python suite pass locally. The latest
full Python run passes 2,570 tests with 5 skips; the committed coverage baseline
is 92.025% statement, 87.690% branch, and 91.030% combined, with a refresh open
to include TASK-146's new regression cases. TASK-144's local
OpenAI adapter differential rejects HTTP 300, 302, and 399 in both languages;
68 focused tests and three Rust adapter unit tests pass, with hosted validation
for TASK-144 running on `0d3ea70`. TASK-145 adds three full-output CLINC150
real-row differentials and is pushed at `d80a6df`; external dataset fetching
remains a documented Partial surface. The matrix has 48/77 full Rust modules;
29 remain Partial, so migration and product acceptance remain incomplete.
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

## TASK-153 recovery — 2026-11-15

Recovered strict bundle redaction in a persistent managed checkout based on c7d8180.
Python focused tests: 88 passed, 1 skipped; Rust CLI library 75/75 and observability
6/6; strict differential 1/1. Full Rust workspace, strict workspace Clippy, Ruff,
formatting, wheel/sdist and installed-wheel init/routing/bundle/API/MCP/plugin smoke
pass. Independent Python and Rust review found no blocking issue. Full Python
regression passes 2,597/7 in 501.42 seconds with 92.004% statement, 87.789%
branch, and 91.034% combined coverage. No thresholds or frozen data changed.
Bundle remains Partial for filesystem and JSON edge-case behavior. TASK-154 will
address reproduced Python artifact overwrite, then evaluation grading/platform
orchestration is next.
