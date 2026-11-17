# Product Acceptance Evidence

## Current checkpoint — 2026-11-17

Product acceptance remains **not granted**. TASK-171 provider refresh parity is
independently clear: deterministic process evidence covers OpenRouter/OpenAI
success and failure semantics, dry-run and malformed-fetch no-write behavior,
provenance, deprecations, manual-registry preservation, OpenAI key gating, and
credential redaction. Inventory: 59 Parity / 18 Partial.

Product acceptance remains **not granted**. TASK-170 packaged annotation CLI
parity is independently clear: embedded candidate/holdout resources, exact
resource evidence, source-independent fallback, and 88 annotation CLI/schema
checks pass. Inventory: 58 Parity / 19 Partial.

Product acceptance remains **not granted**. TASK-169 HTTP lifecycle parity is
independently clear: the executable uses the shared OS-aware home resolver and
114 focused process/schema checks cover request-ID short circuits, auth/rate/
CORS, generic registry errors, and idempotency replay semantics. Full Rust
workspace/Clippy and Python 2,731/7 pass. Inventory: 57 Parity /
20 Partial.

Product acceptance remains **not granted**. TASK-168 observability parity is
independently clear: task-local and synchronous request-context APIs, opt-in
structured events/errors, strict secret redaction, OTel span activation, and
single-emission server error paths pass nine focused Rust tests, full Rust
workspace/Clippy, and Python 2,728/7. Inventory: 56 Parity / 21 Partial.

## Previous checkpoint — 2026-11-16

Product acceptance remains **not granted**. TASK-167 server-service parity is
independently clear: 102 focused checks, active-span wiring, full Rust workspace,
strict Clippy, and Ruff pass. Inventory: 55 Parity / 22 Partial; full Python
regression passes 2,728/7.

Product acceptance remains **not granted**. TASK-166 annotation-schema parity is
independently clear after the public deserialization fail-closed repair. Direct
77 and production-path 108 checks pass with evaluation Rust tests, strict Clippy,
and Ruff. Inventory: 54 Parity / 23 Partial.
Full Rust workspace/Clippy and Python 2,719/7 pass.

Product acceptance remains **not granted**. TASK-164 server-schema parity is
independently clear with 93 focused differentials, API Rust tests, strict Clippy,
and Ruff passing. Full Python regression passes 2,696/7. Inventory: 53 Parity /
24 Partial.

Product acceptance remains **not granted**. TASK-162 runner parity is locally
complete and independently clear: 2,660/7 Python, full Rust workspace/Clippy,
Ruff, and 40 focused checks pass. Inventory: 52 Parity / 25 Partial.

TASK-165 repairs the hosted Windows failures with 46 focused checks and clear
independent review; acceptance remains held pending hosted revalidation.

Product acceptance remains **not granted**. TASK-161's grading row is promoted
after independent review and complete default/injected, both-mode differential
coverage. Full local Python regression passes 2,642/7; Rust workspace, strict
Clippy, Ruff, and 27 focused grading checks pass. The 77-module inventory now
has 51 Parity and 26 Partial rows. Hosted validation and all previously named
release blockers remain.

## Previous checkpoint — 2026-11-15

Product acceptance remains **not granted**. At `5af3c55`, the Python, Rust,
cross-platform compatibility, API, build, security, website, and mutation jobs
pass. The frozen context-band evaluation gate remains 0.6667 < 0.90; PR #16
has no human review, and live OpenAI smoke still needs credentials. TASK-152
adds opt-in, redacted route records to the Rust HTTP service. Full local Python
regression passes 2,590/5 and Rust workspace/Clippy pass; hosted validation
awaits the RC push. The 77-module Rust inventory has
50 Parity and 27 Partial rows.

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

## TASK-154 exclusive artifact creation — 2026-11-15

A support bundle can no longer replace an existing artifact. Python matches
Rust by refusing existing files and symlinks, including a final-path race.
Focused, full-regression, packaged-wheel, and independent-review evidence pass.

## TASK-155 fail-closed holdout grading — 2026-11-15

Supplied malformed holdout evidence now stops Rust grading with an explicit
error. Valid, absent, and JSON-null inputs match Python. Local regression and
independent-review evidence pass without changing evaluation thresholds.

## TASK-156 consistent injected grading — 2026-11-15

When evaluation uses a custom classifier, every dependent scorecard dimension
now measures that same classifier. Default behavior remains unchanged. Local
compatibility, full-regression, and independent-review evidence pass.
## TASK-157 public grading runtime — 2026-11-15

Rust default grading now loads packaged models and queries the installed CLI
without caller manifests. Full Python 2,613/7 and independent review pass;
evaluation/platform parity remains Partial and acceptance is not granted.
## TASK-158 evaluation CLI contracts — 2026-11-15

Measured report, comparison, preparation, status, and context-band CLI paths
now have direct Rust coverage and repaired error behavior. Verification passes;
evaluation CLI remains Partial and product acceptance is not granted.
## TASK-159 platform evaluator parity — 2026-11-15

Platform evaluation is promoted to Parity with independent audit and full
regression evidence. Twenty-eight Partial modules and release blockers remain;
product acceptance is not granted.
