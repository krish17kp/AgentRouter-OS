# EVALUATION_ACCEPTANCE

Acceptance checklist (program §19). A box is `[x]` only with file path + command + result.
`[~]` = implemented but external/full run pending (commands + prerequisites given). `[ ]` = locally actionable, not done.

## Architecture
- [x] Evaluation package — `agentrouter/evaluation/` · `python -c "import agentrouter.evaluation"` OK · 12 modules + 8 adapters.

## Eight dataset adapters
- [x] AgentRouter gold — `adapters/agentrouter_gold.py` · `pytest tests/evaluation/test_agentrouter_gold_adapter.py` → 6 passed · READY, 165 cases.
- [~] CLINC150 — `adapters/clinc150.py` · fixture 12 cases pass · full: `pip install datasets`.
- [~] BANKING77 — `adapters/banking77.py` · fixture 12 cases pass, risk-calibration verified · full: `pip install datasets`.
- [~] MASSIVE — `adapters/massive.py` · fixture 12 (en/hi/fr), language filter verified · full: `pip install datasets`.
- [~] LongBench v2 — `adapters/longbench_v2.py` · fixture 8, 5 buckets · `full_run_status()` gives commands.
- [~] SWE-bench — `adapters/swebench.py` · fixture 6 · full needs Docker + `swebench` harness.
- [~] LLMRouterBench — `adapters/llmrouterbench.py` · fixture 6, `model_mapping_required()`=True.
- [~] TwinRouterBench — `adapters/twinrouterbench.py` · fixture 6 static-track · dynamic needs Docker.

## Provenance & data policy
- [x] Provenance on every case — `evaluation/schema.py::Provenance` · fixtures marked `model_assisted`, gold marked `human`.
- [x] No full datasets committed — only fixtures/gold/benchmarks in git; `data/`, caches ignored in `.gitignore`.
- [x] Dataset-quality/leakage report — `provenance.py::dataset_quality` · `tests/evaluation/test_provenance.py` 5 passed.

## Metrics & grading
- [x] Classification metrics — `metrics.py` · `tests/evaluation/test_metrics.py` 5 passed · acc/macro-F1/per-class/confusion/tool-micro-F1/high-risk-recall.
- [x] 100-point scorecard + gates — `grading.py` · `tests/evaluation/test_grading.py` 5 passed · unmeasured dims honestly 0.
- [ ] Routing / safety / CLI / provider / feedback / performance evaluators — declared **pending** in scorecard; not yet built.

## Baseline
- [x] Captured before classifier change — `artifacts/evaluation/baseline_v0.4.0.{json,md,csv}` · SHA 67548a2.

## Reports
- [x] JSON/MD/CSV/confusion/scorecard — `reports.py` · `pytest tests/evaluation/test_reports_comparison.py` 4 passed.
- [x] Baseline-vs-current comparison — `comparison.py` · `python -m agentrouter eval compare ...` → grade delta + regressions.

## CLI
- [x] list-datasets / validate-dataset / run / report / compare — `evaluation/cli.py` · `pytest tests/evaluation/test_evaluate_cli.py` 6 passed · all commands run offline.

## Tooling
- [x] pytest markers registered — `pyproject.toml`.
- [x] Branch coverage — `pytest --cov=agentrouter --cov-branch` → 86.92%.
- [x] Ruff — `ruff check . && ruff format --check .` clean.
- [x] Optional extras — `pyproject.toml` eval/property/security/benchmark/mutation/ops/all-eval.
- [ ] Hypothesis property tests (beyond existing 6 invariants).
- [ ] Promptfoo local provider.
- [ ] mutmut config + WSL docs.
- [ ] Bandit + pip-audit + secret-scan job.
- [ ] pytest-benchmark suite.
- [ ] DVC pipeline + local MLflow.
- [ ] Extra GitHub Actions (fast/nightly/security/mutation/full-dispatch).

## Platform
- [x] Windows — full suite green locally (win32, py3.13).
- [~] Linux + py3.10–3.13 — offline, no new native deps; expected green in CI (not run this session).

## Policy
- [x] No secrets in code/fixtures/reports.
- [x] No Git writes performed.

**Not finishable-as-complete:** routing/safety/etc. evaluators, 500-case benchmark + review workflow, Promptfoo/mutmut/Bandit/DVC/MLflow, extra CI. See `EVALUATION_HANDOFF.md`.
