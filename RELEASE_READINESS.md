# Release Readiness

## Current checkpoint — 2026-11-15

**NOT release ready.** At `5af3c55`, the hosted cross-platform Python and Rust
matrices, API, build, security, website, and critical mutation pass. PR #16 is
the sole open PR, has no GitHub review, and fails the unchanged frozen
context-band gate at 0.6667 < 0.90. Live OpenAI smoke skips without owner
credentials. Rust migration is 48/77 full-module parity with 29 Partial rows;
TASK-152 route observability passes local full Python/Rust regression: 2,590/5
Python tests at 92.052% statement, 87.756% branch, and 91.064% combined
coverage; Rust workspace, strict Clippy, wheel build, and clean-wheel smoke pass.
Hosted TASK-152 validation awaits the RC push. Main promotion, tag,
and production deployment remain blocked by the documented gates and owner
inputs.

## Previous checkpoint — 2026-11-14

**NOT release ready.** At last pushed code head `9a7dc7a`, Rust workspace checks
pass on Linux/Windows/macOS and Python/Rust compatibility passes on Linux/macOS;
Windows compatibility and most Python/platform jobs are still running. The PR
workflow's enforcing gate fails at frozen context-band accuracy 0.6667 versus
0.90; the push workflow skips it. TASK-149's nested redaction differential is
in hosted validation. TASK-150's large-integer response parity and full Python
regression pass locally and await hosted checks. PR #16 has no GitHub reviews.
Live smoke skips without an OpenAI credential.

TASK-140's Rust SDK wire-contract comparison passes all nine endpoints with
present, absent, and blank API keys. TASK-141 adds an injected transport and
timeout seam, all-nine-operation `httpx.MockTransport` comparisons, typed
transport categories, idempotent close, fail-closed fixture input validation,
and credential-safe URL/body diagnostics. The focused SDK/reliability selection
passes 52 Python tests and ten Rust SDK unit tests; full Rust workspace, strict
Clippy, formatting, Ruff, and the full Python suite pass locally. The latest
Python regression is 2,580 / 5; the committed TASK-150 coverage report measures
92.030% statement, 87.712% branch, and 91.038% combined coverage.
Current hosted cross-platform validation is still running; the latest completed
code-head run passes the Python Linux 3.10–3.13 matrix and Rust/Python
compatibility on all three platforms. TASK-144 locally aligns Python and Rust
OpenAI adapters for every non-2xx response; its offline differential cases and
68 focused Python tests pass.
TASK-145 adds three direct CLINC150 normalization comparisons; the Rust adapter
transformation matches Python, while external Hugging Face loading remains
Partial. TASK-147 bounds native TCP connection setup using the configured SDK
timeout while preserving the whole-request deadline. The SDK remains Partial
for the wider `ureq` timeout model and generic read/write behavior. PR
#16 remains the sole open PR. Rust
CLI/HTTP/MCP parity, provider execution, external dataset loaders, evaluation
runner, and R5–R13 remain incomplete. Human annotation, live OpenAI validation,
main promotion, and production credentials remain owner inputs. No paid request
or production deployment occurred.

## Historical v0.5 assessment

**Status: NOT release-ready.** Canonical v0.5 release-candidate assessment,
updated 2026-08-08 (iter26, after TASK-011/012/013/014/015/016 merged to
`release/agentrouter-v0.5-rc1`, RC @ `5847c22`).

The **only** remaining blocker is the frozen held-out context-band gate. It cannot
be closed by tuning — it needs the human-labelled dataset that TASK-011 tooling and
TASK-012 operations produce. The gate and its 0.90 threshold are unchanged.

## Current evidence

| Gate | State | Evidence |
|---|---|---|
| Offline routing and exact model/host output | Pass | Routing and CLI suites (RC) |
| High-risk execution and injection protections | Pass | Safety, execute, injection suites |
| Evaluation grade | Pass | ~98/100 canonical run; 6/7 gates pass |
| Six non-context evaluation gates | Pass | `artifacts/evaluation/result.json` |
| Frozen held-out context generalization | **Fail (by design)** | 0.6667 accuracy vs unchanged 0.90 threshold (shipped rules-active; TASK-009 proved the 24-case dev set is a ceiling) |
| Critical-module mutation thresholds | **Pass** | Linux mutmut 3.6.0, 923 mutants: overall 0.9837; safety_policy_execution 0.985 (>=0.95); routing_engine 0.9815 (>=0.85); no safety/policy/execution-bypass survivor |
| Safe reversible plugin lifecycle | Pass | Plugin suites green |
| Full local matrix | Pass | `pytest` 684 passed, 3 env-skips + 33 hook tests (2026-08-08; local env watchdog issue resolved) |
| Linux/Windows GitHub checks | Pass; enforce-release-gate correctly gated to promotion only | CI matrix 3.10-3.13 + test-windows + build-smoke + Security + release-readiness-report + Critical Mutation Testing green on RC @ `5847c22`; `enforce-release-gate`/`live-smoke` skip on task/RC pushes by design (TASK-014) |
| Dependency audit | Pass | `pip-audit -r requirements.txt`: no known vulnerabilities |
| Clean wheel install/lifecycle | Pass (re-verified 2026-08-08) | Wheel builds; installed into a fresh venv outside the repo; `providers status/doctor/rollback/restore` + `route` exercised, incl. corrupt-catalog exit 3 |
| Context-band dataset program | Delivered (labels pending) | TASK-011/012 merged; final human labels are the external TASK-012 step |
| Catalog trust + reversibility | Delivered | TASK-013 + TASK-015 merged: provenance block, atomic refresh, deprecation reporting, rollback/restore, `providers doctor`; security review 0 critical, all medium/low fixed |
| CI release-gate semantics | Delivered | TASK-014 merged; report (non-enforcing) vs enforce (promotion-only) split |

The 0.945 value previously used for context readiness came from the 165-case
in-sample gold set. The canonical generalization gate now uses the frozen,
checksum-locked 45-case holdout and is deliberately not tuned after its final run.

## External production prerequisites

Live provider verification, paid-model benchmarking, hosted deployment,
marketplace publication, beta feedback, and operational sign-off still require
credentials, budget, infrastructure, or owner decisions. These do not excuse the
three local/CI blockers above.

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

Local release evidence passes: focused 95/1, full Python 2,604/7, 92.021%
statement and 87.833% branch coverage, independent review, hooks, Bandit,
wheel/sdist build, and installed-wheel exclusive-create smoke. Hosted
validation follows the RC push. Overall release readiness remains held by the
existing frozen evaluation and external requirements.
