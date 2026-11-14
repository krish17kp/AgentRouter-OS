# Release Readiness

## Current checkpoint — 2026-11-14

**NOT release ready.** Pushed RC head `b244ad1` has failing Windows Rust,
Windows compatibility, macOS Rust, and mutation checks. The local TASK-114
candidate repairs the observed cross-platform failures and implements Rust
managed plugin upgrades. Its full mutation campaign passes at 0.9698 overall,
0.9670 safety/policy/execution, and 0.9815 routing, with zero unreviewed
survivors; exact evidence is in
`docs/MUTATION_REPORT_2026-11-14-TASK-114.md`. The full Python regression
on pytest 9.0.3 passes 2,262 tests with 4 skips (91.96% statement, 87.65% branch,
90.97% combined). The Rust workspace, strict Clippy, Ruff, formatting, Bandit,
cargo audit, package wheel/sdist build, and Twine metadata checks pass. `pip-audit`
initially found vulnerable development-only pytest 8.4.2; the constraint now
requires patched pytest 9.0.3–9.0.x and `pip-audit` is clean. Hosted
cross-platform confirmation is pending the next release-candidate push. PR #16 remains the
sole open PR.
The unchanged context-band score is 0.6667 < 0.90; live smoke is skipped
without credentials. Full Rust CLI/HTTP/MCP parity, provider execution,
external dataset loaders, evaluation runner, and R5–R13 remain incomplete.
Human annotation, live OpenAI validation, main promotion, and production
credentials remain owner inputs. No paid request or production deployment
occurred.

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
