# Assignment B — Real Model Catalog, Host-Aware Routing, Execution

Status of the command.md Assignment B (lines 93–1027). `[x]` done+verified ·
`[~]` partial/handed-off · `[ ]` not started. No git operations performed.

- **CI at start:** green (SHA b48a3b5) — the earlier Linux failure was already fixed; nothing to repair.
- **Tests:** 276 passed (264 prior + 12 new), branch coverage 81.85% (>80% gate), ruff clean.
- **Backward compat:** all prior tests still pass; JSON keeps legacy keys; `vendor` defaults to `provider`.

| Phase | Item | Status | Evidence |
|-------|------|--------|----------|
| 1 | Vendor vs execution-host schema | [x] | `schema.py`: `ExecutionTarget`, `ModelEntry.vendor/execution_targets/provenance`, `vendor_key`; `vendor` defaults to `provider` (migration) |
| 2 | Replace placeholder seeds with real models | [x] | `seeds/models.yaml`: Claude Fable5/Opus4.8/Sonnet5/Haiku4.5 + GPT-5.6 Sol/Terra/Luna, curated ability + provenance; `test_no_placeholder_ids_in_production_seed` |
| 3 | Dynamic catalogs (`models refresh` for 4 vendors) | [~] | `models list`/`show` done; refresh adapters for anthropic/google + real OpenAI/OpenRouter join NOT built (needs live APIs) — legacy `providers refresh openrouter/openai` still works |
| 4 | Host discovery (`hosts list/doctor/show`) | [x] | `hosts.py` + `hosts` sub-app; shutil.which + env checks; available/unavailable/unknown |
| 5 | Two-stage routing (model → host) | [x] | `_execution_route` + `hosts.resolve_execution_route`; stage 1 (engine) unchanged, stage 2 added |
| 6 | Detailed terminal output + JSON `execution_route` | [x] | `_print_exec_block`; JSON adds `execution_route`/`fallback_execution_route` (additive) |
| 7 | Exact execution via host | [x] | `_execute_via_host`: argv/shell=False, `--dry-run`, `--yes`, high-risk block preserved, unavailable-host refusal, exit-code propagation |
| 8 | Route control flags (`--vendor`, `--host`, `--prefer-*`, `--stable-only`, …) | [ ] | not built — existing `--risk/--tool/--context-tokens` overrides remain |
| 9 | Model-specific measured scoring | [~] | provenance fields exist (`ability_source`, `ability_confidence`); seeds marked `curated`; measured-benchmark integration NOT wired |
| 10 | Tool taxonomy expansion | [ ] | classifier taxonomy unchanged (separately tested; deferred to avoid destabilizing it) |
| 11 | Tests | [~] | `test_model_catalog.py` (11) + execute tests updated; ~14 of the 30-point matrix covered — full matrix (refresh determinism, stale warnings, preview-policy, old-decision replay) pending |
| 12 | CI repair + verification | [x] | CI already green; ruff + 276 tests + route/execute smoke verified locally; `python -m build` NOT re-run this session |

## What works now (offline, no keys)
```
agentrouter route "build a rag system ..."        # -> real model + vendor + host + fallback
agentrouter models list [--available]
agentrouter models show anthropic/claude-sonnet-5
agentrouter hosts list | doctor | show claude-code
agentrouter execute <id> --dry-run                # exact command preview, prompt redacted
agentrouter execute <id> --yes                    # runs exact model via available host; high-risk blocked
```

## Verified routing (Phase 12)
- "build a rag system…" → **GPT-5.6 Luna** (openai) via openai-api; fallback **Claude Sonnet 5** via claude-code.
- "fastapi … scraping automation" → **GPT-5.6 Luna** via openai-api.
- "Refactor the payment module and add unit tests" → **Claude Opus 4.8** via claude-code (risk=high → execution blocked).

## Honest limitations / handoff
- **Phase 3** dynamic refresh adapters (anthropic/openai/google Models APIs, OpenRouter `/api/v1/models` with full metadata) are NOT implemented — they need live authenticated APIs + a large mocked-test surface. Google/OpenRouter catalogs therefore ship only via the existing legacy `providers refresh` path; the new-schema `models refresh` is a stub to build.
- **Phase 8** route-control flags, **Phase 10** tool-taxonomy expansion, and the remainder of the **Phase 11** 30-point matrix are not done.
- Ability scores are **curated guesses** (`ability_source: curated`, low confidence), NOT benchmarks — replace with measured values (Phase 9) before trusting rankings.
- Model IDs/limits for Anthropic + OpenAI are taken from the command's explicit spec; Google/OpenRouter intentionally omitted rather than guessed.
- Git policy honored: no add/commit/push/tag/PR.
