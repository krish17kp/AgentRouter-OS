# Product Acceptance Evidence

Only items with real, current evidence are marked done. "Done" = implementation +
tests + user-facing workflow + negative path + docs (command.md §8).

## Phase P3 — route controls (this loop)

| Requirement | Impl | Test | Verify command | Status |
|-------------|------|------|----------------|--------|
| `--vendor` / `--exclude-vendor` | `controls.py` | `test_vendor_filter_case_insensitive`, `test_exclude_vendor_drops_that_vendor`, `test_cli_vendor_flag_scopes_recommendation` | `pytest tests/test_route_controls.py` | ✅ |
| `--model` pin | `controls.py` | `test_model_pin_keeps_only_match`, `test_model_pin_matches_bare_id`, `test_cli_model_pin_selects_that_model` | ↑ | ✅ |
| `--host` / `--exclude-host` | `controls.py` | `test_host_filter_keeps_only_models_on_host` | ↑ | ✅ |
| `--stable-only` / `--allow-preview` | `controls.py` + `cli.py` | `test_stable_only_drops_non_stable`, `test_cli_stable_only_and_allow_preview_conflict` | ↑ | ✅ |
| `--available-only` / `--include-unavailable` | `controls.py` + `cli.py` | (conflict path) `test_cli`… | ↑ | ✅ |
| `--max-price` (honest, excludes unknown) | `controls.py` | `test_max_price_excludes_unknown_price_honestly` | ↑ | ✅ |
| `--prefer-quality/cheap/fast/balanced` | `engine.py` + `cli.py` | `test_preference_vectors_sum_to_one`, `test_cli_prefer_quality_beats_default_on_simple_task`, `test_cli_conflicting_prefer_flags_is_usage_error` | ↑ | ✅ |
| Impossible filter → no-model exit 4 | `cli.py` | `test_cli_impossible_filter_reports_no_model` | ↑ | ✅ |
| Backward compat (empty controls) | `controls.py` | `test_empty_controls_keeps_everything` + all 276 prior | `pytest -q` → 291 passed | ✅ |

## Phase P3 — confidence & abstention (iteration 2)

| Requirement | Impl | Test | Status |
|-------------|------|------|--------|
| Confidence score | `classifier._confidence` | `test_clear_task_is_high_confidence`, `test_confidence_is_bounded` | ✅ |
| `needs_clarification` abstention | `classifier.classify` + `cli._print_route` | `test_vague_task_...`, `test_cli_text_shows_low_confidence_note` | ✅ |
| Alternative interpretation | `_task_type_families` | `test_competing_families_surface_an_alternative` | ✅ |
| `--uncertainty-threshold` | `cli.route` | `test_threshold_controls_clarification_flag` | ✅ |
| JSON exposes fields | schema (additive) | `test_cli_json_exposes_confidence_fields` | ✅ |

**Still deferred in P3:** `--privacy local-only`, `--max-estimated-cost` (see KNOWN_LIMITATIONS.md).

## Phase P8 — plugin/skill installer (iteration 3)

| Requirement | Impl | Test | Status |
|-------------|------|------|--------|
| `plugin list` + status | `plugins.status`, `cli.plugin_list` | `test_cli_install_and_uninstall_roundtrip` | ✅ |
| Install (create) | `plugins.install` | `test_install_creates_file` | ✅ |
| Idempotent reinstall | `plugins.install` | `test_install_is_idempotent` | ✅ |
| Safe: no clobber without `--force` | `plugins.install` | `test_install_refuses_to_clobber_without_force` | ✅ |
| Reversible: backup + restore on uninstall | `plugins.install/uninstall` | `test_force_backs_up_then_uninstall_restores` | ✅ |
| Uninstall removes created file | `plugins.uninstall` | `test_uninstall_removes_created_file` | ✅ |
| `--dry-run` / `doctor` changes nothing | `plugins.plan` | `test_plan_changes_nothing` | ✅ |
| Unknown plugin → usage error | `cli._resolve_plugin` | `test_cli_unknown_plugin_is_usage_error` | ✅ |
| Ships in wheel | `pyproject` package-data | `build --wheel` → payloads present (manual) | ✅ |

**Deferred in P8:** MCP server, `/route*` slash commands, examples/ templates, Linux-CI install run.

## Phases P4 / P9 / P10 / P6 / P7 (iterations 5-7)

| Phase | Requirement | Impl | Test | Status |
|-------|-------------|------|------|--------|
| P4 | Versioned taxonomy + alias eligibility + `--prohibit-tool` | `taxonomy.py`, `engine.eligibility`, `controls.py` | `tests/test_taxonomy.py` (14) | ✅ |
| P9 | `setup` wizard (non-interactive, secret-safe) | `cli.setup` | `tests/test_setup.py` (5) | ✅ |
| P10 | URL-scheme guard; bandit/pip-audit/secret CI | `refresh._http_get_json`, `.github/workflows/security.yml` | `tests/test_security_scan.py` (5) | ✅ |
| P6 | 6 evaluators + `eval run --all` (100-pt) | `evaluation/evaluators/*`, `grading.grade(measure_all)` | `tests/evaluation/test_evaluators.py` (13) | ✅ (grade 96.89; 2 gates fail honestly) |
| P7 | Local REST API (9 `/v1` endpoints, no remote exec) + Python SDK | `agentrouter/server/*`, `sdk.py`, `cli.server` | `tests/test_server.py` (27) + `tests/test_sdk.py` | ✅ |

**Session totals:** 276 → 371 tests (+95). ruff+format clean. bandit 0 issues. pip-audit 0 vulns.
Wheel 0.4.0 builds with all subpackages + data.

**Honest gaps:** TypeScript SDK, MCP server, structured logging/OpenTelemetry, rate-limit
enforcement, testing-stack extras (Hypothesis/mutmut/DVC/MLflow), and the 2 failing eval gates.
External-blocked: P1/P2/P5/P11/P13/P14 (credentials, paid inference, infra, real beta).
