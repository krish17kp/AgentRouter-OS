# Quality Dashboard — AgentRouter OS

## Current checkpoint — 2026-11-11

RC `07eb511` includes the website redesign, macOS Python/Rust CI, routing
benchmark/coverage evidence, Rust dashboard/OpenAI helpers, harness parity, and
dependency hardening. PR #13 plugin mutation campaign is green locally
(1,629 selected mutants; 0.9693 overall, 0.9663 safety/policy/execution,
0.9815 routing; zero unreviewed survivors); PR #13 was merged after all checks
passed. The latest full Python run passed
1,720 tests with 6 skips and measured 91.01% line / 85.23% branch coverage,
meeting the unchanged 90%/85% thresholds. Rust workspace tests, formatting,
Clippy, and `cargo audit --deny warnings` pass locally; bundled SQLite is 3.54.1
and `unsafe-libyaml` has been removed. A local Rust diagnostic-bundle parity
slice now withholds all environment values except the resolved home path; its
focused tests and Linux/Windows/macOS CI passed on `07eb511`. The latest local
slice adds quota-aware Rust reranking with ten differential cases and
Python-compatible Unicode sanitation; fresh CI is pending. Context-band
accuracy remains 0.6667 < 0.90; Rust R4 and R5–R13 remain
incomplete. This project is not release-ready.

## Historical dashboard

_Last refreshed: 2026-08-08 (iter26, after TASK-011/012/013/014/015/016 merged to
the RC @ `5847c22`). Current measurements supersede historical TASK-004 in-sample
readiness claims._

| Dimension | Current state | Evidence |
|---|---|---|
| Python tests | Pass | `pytest` 684 passed, 3 env-skips (2026-08-08, local); includes TASK-011/012/013/015/016 tests; local env watchdog issue that previously killed multi-second runs is resolved |
| TypeScript SDK | Pass (prior session) | `npm test` 8/8 and `npm run typecheck`; unaffected by TASK-015 |
| Hooks | Pass | `.claude/hooks/test_hooks.py`: **33 passed** (git guardrail allow/block matrix) |
| Lint | Pass | Ruff check + format clean across the tree (verified 2026-08-08) |
| Dependency audit | Pass | `pip-audit -r requirements.txt`: no known vulnerabilities (2026-08-08) |
| Evaluation grade | ~98/100 | `python -m agentrouter eval run --all --out-dir artifacts/evaluation` |
| Evaluation gates | **6/7; release readiness NO** | Frozen 45-case context holdout accuracy 0.6667 (rules-active), below the unchanged 0.90 threshold |
| Mutation | **Pass** | Linux mutmut 3.6.0, 923 mutants: overall 0.9837; safety_policy_execution 0.985; routing_engine 0.9815; no safety/policy/execution-bypass survivor |
| Security | Pass | Bandit 0 (config-aware, verified locally 2026-08-08) + pip-audit green on RC CI |
| Packaging | Pass (re-verified 2026-08-08) | Wheel + clean-venv smoke outside the repo: `providers status/doctor/rollback/restore`, `route`, packaged resources |
| GitHub CI (RC) | Pass; enforce-release-gate correctly gated to promotion only | Matrix 3.10-3.13 + test-windows + build-smoke + Security + release-readiness-report + Critical Mutation Testing green on `5847c22`; `enforce-release-gate`/`live-smoke` skip on task/RC pushes by design (TASK-014) |
| Context-band dataset program | Delivered | TASK-011/012 merged (annotation CLI, adjudication, leakage-safe splits, comparison); final human labels are the external TASK-012 step |
| Catalog trust + reversibility | Delivered | TASK-013 + TASK-015 merged: provenance block, atomic refresh, deprecation reporting, rollback/restore, `providers doctor` |
| CI release-gate semantics | Delivered | TASK-014 merged: report/enforce split |
| Security review (TASK-015 diff) | Pass | Independent review: 0 critical, 3 medium, 2 low; all medium+low fixed and regression-tested (symlink-race, crash-on-corruption, backup-rotation data loss) |

## Canonical evaluation gates

- `task_type_macro_f1>=0.90`: PASS
- `high_risk_recall==1.00`: PASS
- `approval_accuracy==1.00`: PASS
- `tool_needs_f1>=0.90`: PASS
- `context_band_accuracy>=0.90`: **FAIL (0.6667; shipped rules-active)**
- `high_risk_gated==1.00`: PASS
- `synthetic_routing_top1>=0.95`: PASS

The former 0.945 context value is explicitly labeled as in-sample gold-set
accuracy in the current report. It is not evidence of held-out generalization.

## Open release blockers

- Frozen held-out context-band accuracy (0.6667) is below the unchanged 0.90
  threshold. This is the sole remaining blocker; it needs the human-labelled
  dataset from TASK-011 tooling + TASK-012 operations, not tuning.
- (Resolved) Linux mutation score: overall 0.9837, all gates pass.
- (Resolved) Full verification matrix + release-branch GitHub checks: green except
  the honest release-gate above.
