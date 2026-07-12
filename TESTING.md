# Testing AgentRouter OS

## Run everything

```console
pip install -e ".[dev]"
pytest                            # all tests, offline, < 5s
pytest --cov=agentrouter          # with coverage; fails under 80%
```

No test needs internet or an API key — provider-refresh tests monkeypatch the
HTTP layer. CI (`.github/workflows/ci.yml`) runs the same commands on Python
3.11/3.12/3.13.

## Test layout

| File | Covers |
|---|---|
| `tests/test_mvp.py` | Classifier (incl. docs-vs-coding regressions), registry validation, eligibility filters, scoring, safety gates, route/explain end-to-end, error-path UX, JSON contract |
| `tests/test_refresh.py` | OpenRouter refresh: mapping, pricing tiers, mocked HTTP, dry-run, network-error handling, manual-wins merge, idempotency, key hygiene |
| `tests/test_cli_smoke.py` | Entrypoints (`python -m agentrouter --help`, `--version`), command listing, fresh-user init → list → route flow |
| `tests/test_stats.py` | M7 telemetry: aggregates, per-user history, pre-M7 DB migration, policy pricing cap, `pricing_tier` in route JSON |

## Post-build verification (runs in CI on every push)

The `build-smoke` CI job builds the real sdist + wheel, installs the wheel
into a **clean venv**, and smoke-tests the installed artifact:
`--version` → `init` → `route --json` (asserts a recommendation) → `stats` →
`registry list`. This catches packaging bugs (missing seed YAMLs, broken
entrypoints) that editable installs never hit. Run it locally with:

```console
python -m build
python -m venv /tmp/wheelenv && /tmp/wheelenv/bin/pip install dist/*.whl
AGENTROUTER_HOME=/tmp/arhome /tmp/wheelenv/bin/agentrouter init
```

## Conventions

- Isolated home: tests set `AGENTROUTER_HOME` to a tmp dir — they never touch
  your real `~/.agentrouter/`
- Mock at the seam: refresh tests replace `agentrouter.refresh._http_get_json`,
  nothing deeper
- Classifier changes need a regression test (see `DOC_TASKS` parametrization)
- AAA structure, descriptive names, no sleeps/flaky waits

## Live smoke test (manual, optional — not part of pytest)

```console
agentrouter providers refresh openrouter --limit 5 --dry-run
```

Needs internet; works without a key (public catalog endpoint).
