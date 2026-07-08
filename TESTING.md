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
| `tests/test_cli_smoke.py` | Entrypoints (`python -m agentrouter --help`), command listing, fresh-user init → list → route flow |

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
