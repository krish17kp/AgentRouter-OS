# Release check

| Requirement | Impl | Test | Command output | Docs |
|---|---|---|---|---|
| Harness identity, evidence-only | `agentrouter/harness.py` | `tests/test_harness.py` (9 tests) | `agentrouter doctor` shows `[OK] environment.harness claude-code (CLAUDECODE env var is set)` in this real session | module docstring |
| Usage default UNKNOWN, live UNSUPPORTED, never fabricated | `agentrouter/usage.py:check_usage` | `tests/test_usage.py` (18 tests) | `doctor --verify-live` with a fake `OPENAI_API_KEY` shows `unsupported: no live usage check registered for 'openai'` | module docstring |
| doctor always runs harness; --verify-live isolates provider failures | `diagnostics.py:run_all/run_usage_checks` | `tests/test_diagnostics.py` (11 new tests, incl. a crashing-check isolation test) | verified: crashing check keeps others visible, no Traceback | doctor `--help` |
| route --verify-live re-ranks EXHAUSTED, explains why | `usage.py:apply_live_verification`, `cli.py:_reason_for` | `tests/test_usage.py` re-rank tests, `tests/test_cli_smoke.py` | live CLI run: `route --verify-live --json` payload includes `usage_check`; plain `route --json` does not | route `--help` |
| No secret ever printed | traced every new string sink | `test_harness_check_is_always_present_and_never_a_secret_leak`, `test_a_registered_check_cannot_inject_control_characters_or_ansi_escapes` | fake key absent from all doctor output, confirmed live | n/a |
| Zero default-behavior change | additive flags/fields only | `test_verify_live_is_opt_in_and_absent_by_default`, `test_route_without_verify_live_has_no_usage_check_field` | full regression 970 passed / 3 skipped (baseline 936/3, so +34 new tests, 0 regressions) | n/a |

**Verdict per gate**: PASS on every criterion in task.yaml, post-repair. No
CRITICAL/HIGH finding at any point. This task does not touch, and does not
move, the RC's overall `context_band_accuracy` release gate (still 0.6667,
unchanged, human-annotation-gated per `TASK_012_OWNER_ACTIONS.md`) — this
milestone's own scope is release-ready on its own criteria; the RC as a whole
remains NOT RELEASE READY for the pre-existing, unrelated reason.

**Final commands, this session, post-repair**:
- `pytest -q` → 970 passed, 3 skipped
- `pytest tests/test_harness.py tests/test_usage.py tests/test_diagnostics.py tests/test_host_states.py tests/test_cli_smoke.py -q` → 82 passed
- `ruff check . && ruff format --check .` → clean, 348 files
- `bandit -c pyproject.toml -r agentrouter` → 0 issues
- `pip-audit -r requirements.txt` → no known vulnerabilities
- Real-environment smoke: `agentrouter init` → `doctor` (1.13s) → `doctor --verify-live` (0.98s) → `route ... --verify-live` — all truthful, no secrets, fast.
