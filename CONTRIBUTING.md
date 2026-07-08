# Contributing to AgentRouter OS

## Dev setup

```console
git clone https://github.com/krish17kp/AgentRouter-OS.git
cd AgentRouter-OS
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -e ".[dev]"           # project + pytest, pytest-cov, ruff
```

## Before you push

CI runs exactly these; run them locally first:

```console
ruff check .                      # lint
ruff format --check .             # formatting (fix with: ruff format .)
pytest --cov=agentrouter          # tests + 80% coverage gate
```

All tests are offline — no network, no API keys. Provider-refresh tests use
mocked HTTP. Keep it that way: new tests must not depend on live internet.

## Secrets

Never commit secrets. Real keys go in an untracked `.env` or your shell
environment; `.env.example` holds placeholders only. See
[SECURITY.md](SECURITY.md).

## Conventions

- Python 3.10+; ruff enforces style (line length 100) — no debates
- Commit messages: `<type>: <description>` (feat, fix, refactor, docs, test, chore, perf, ci)
- No model names hardcoded in logic — the YAML registry is the only catalog
- Errors tell the user *what happened, why it matters, what to do next*
- The router plans; it never executes. Keep it that way.

## Where things live

| Area | Files |
|---|---|
| CLI commands | `agentrouter/cli.py` |
| Classification | `agentrouter/classifier.py` (+ regression tests in `tests/test_mvp.py`) |
| Scoring / eligibility | `agentrouter/engine.py` |
| Registry schema + loading | `agentrouter/schema.py`, `agentrouter/registry.py` |
| Provider refresh | `agentrouter/refresh.py` (+ `tests/test_refresh.py`) |
| Safety gates | `agentrouter/safety.py` |
| Decision log | `agentrouter/store.py` |

Design docs: [ARCHITECTURE.md](ARCHITECTURE.md), [ROUTING_RULES.md](ROUTING_RULES.md),
[MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md), [PROVIDER_ADAPTER_SPEC.md](PROVIDER_ADAPTER_SPEC.md).
