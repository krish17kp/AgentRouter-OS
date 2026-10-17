# Testing AgentRouter OS

> **Implementation status:** this strategy and its thresholds (80% branch
> coverage gate, 95%/85% mutation gates) apply to the **Python implementation**
> and are the release-gate authority today. They carry over unchanged as the
> acceptance bar for the approved Rust-native port — see
> [RUST_MIGRATION_PLAN.md](RUST_MIGRATION_PLAN.md) — which must identify and
> validate its own equivalent tooling (e.g. `cargo-mutants`, `cargo-audit`)
> rather than assume these numbers transfer mechanically.

## Run everything

```console
pip install -e ".[dev]"
pytest                            # all tests, offline, < 5s
pytest --cov=agentrouter          # with coverage; fails under 80%
agentrouter eval context-band-generalization
agentrouter eval run --all --require-release-ready
```

The context-band command scores a development split and a checksum-locked final holdout, reports
accuracy, macro-F1, per-band recall and confidence intervals, and compares the frozen pre-TASK-004
rules with the current classifier. `agentrouter eval run --all` uses final-holdout accuracy for the
existing `context_band_accuracy>=0.90` gate; the other six release gates are unchanged.
`--require-release-ready` turns any failed gate into a nonzero exit for CI/release enforcement.
The current frozen-holdout accuracy is 0.5778, so this command intentionally fails until a future
development-only classifier revision generalizes past the unchanged 0.90 threshold.

Linux mutation CI is bounded to critical modules:

```console
pip install -e ".[dev,property,server,mutation]"
python scripts/run_mutation_ci.py --timeout-seconds 2100 --max-children 4
```

Mutmut is pinned to 3.6.0. Native Windows execution is not a valid substitute; the authoritative
score and report come from `.github/workflows/mutation.yml` on Ubuntu.

No test needs internet or an API key — provider-refresh tests monkeypatch the
HTTP layer. CI (`.github/workflows/ci.yml`) runs the same commands on Python
3.10/3.11/3.12/3.13.

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

## Rust migration verification (R1/R2, not the production release gate)

The Rust workspace is being introduced behind the existing Python interfaces.
`/.github/workflows/rust-ci.yml` is **not** a release gate substitute; Python
and the seven evaluation gates retain release authority until full parity.

```console
cargo build --workspace --locked
cargo test --workspace --locked
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
python -m pytest -q tests/test_rust_compat.py tests/test_rust_registry_compat.py
```

CI runs the Rust workspace on Linux and Windows and Python/Rust compatibility
on Linux with Cargo explicitly installed, so those tests cannot silently skip.
R1 CI passed on 2026-10-17; R2 results must be recorded before any promotion.
