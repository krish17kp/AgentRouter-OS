# Release Readiness

**Status: NOT ready for public beta.** Recalculated from current evidence, not prior claims.

## Public-beta gates (command.md P13 / §16)
| Gate | State | Evidence |
|------|-------|----------|
| No production placeholder model IDs | ✅ | `test_no_placeholder_ids_in_production_seed` |
| Exact model + host shown | ✅ | `execution_route` in route JSON |
| Offline route works | ✅ | route runs with no network/keys |
| High-risk execution blocked | ✅ | `test_execute*`; high-risk never auto-executes |
| No shell injection | ✅ | `test_execute_injection.py` (argv, shell=False) |
| Catalog refresh failure atomic | ⚠️ unverified | needs live-refresh tests (P1, blocked) |
| Full 100-point evaluator | ✅ | all 6 evaluators implemented; `eval run --all` → 96.89/100 |
| Overall grade ≥ 85 / macro-F1 ≥ 0.90 / high-risk recall 1.0 | ✅ | grade **98.08**; macro-F1 ✅; high-risk recall 1.0 ✅; `high_risk_gated`==1.0 ✅ (safety-evaluator over-strict bug fixed) |
| Synthetic routing top-1 ≥ 0.95 | ✅ (proxy) | gate now set at ≥0.95 per spec; value 1.0 — **proxy** (no gold routing target until P5) |
| context_band_accuracy ≥ 0.90 (beyond-spec internal check) | ⚠️ 0.82 | improved 0.76→0.82 via principled existing-code context heuristic; not a command.md P13 gate; one-line-prompt band inference has a natural ceiling — not overfitted to force a pass |
| Windows + Linux green in CI | ⚠️ | local Windows green; CI status not checked this loop |
| Wheel install verified | ⚠️ | `python -m build` not re-run this loop |
| One-command plugin install/uninstall | ✅ | `agentrouter plugin install/uninstall` (P8), Windows-verified, in wheel |
| Bandit / pip-audit / secret scan | ✅ (local) | bandit `-c pyproject.toml -r agentrouter` → 0 issues; pip-audit → 0 vulns; secret-scan + security CI workflow added. CI run pending merge. |

## Production gates (P14)
All pending — real beta feedback, holdout, runbook, rollback/backup verification,
hosted-mode isolation, security sign-off. None met.

**Blocking themes:** evaluation completeness (P6), live catalog/host verification
(P1/P2, external-blocked), plugin installer (P8), security scan wiring (P10).
