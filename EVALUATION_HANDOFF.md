# EVALUATION_HANDOFF

The program is large; this session built and **verified** the framework foundation.
This file lists exactly what remains and the next concrete step for each, so the
work can resume cleanly. No git operations were performed.

## Completed & verified this session
- Evaluation package `agentrouter/evaluation/` (schema, base adapter, sampling, provenance,
  registry, metrics, grading, reports, comparison, runner, CLI).
- All 8 dataset adapters (1 real + 7 fixture-backed) with honest `SKIPPED_EXTERNAL` full-run status.
- Classification metrics + 100-point scorecard with pending-dimension honesty + release gates.
- 92 new tests (257 total), coverage 86.92% branch, ruff clean.
- Baseline captured; `.gitignore`, optional extras, pytest markers wired.
- `agentrouter eval {list-datasets,validate-dataset,run,report,compare}` all work offline.

## Remaining — locally actionable (no external deps)
1. **Routing evaluator (25pt)** — build `evaluation/routing_eval.py` using a synthetic registry
   + `engine.route`; grade eligibility/ranking/fallback/pricing/explain/tie. Wire into `grading.py`
   as a measured dimension. Next: model the synthetic registry from program §10.
2. **Safety evaluator (15pt)** — reuse `tests/test_execute_injection.py` + `safety.gates_for`;
   grade "high-risk always blocked", secret-leak, injection, malformed-config. Wire into `grading.py`.
3. **CLI/provider/feedback/perf evaluators (10+8+7+5)** — mostly assert-existing-behaviour; convert
   to scored dimensions.
4. **Hypothesis** — `pip install -e ".[property]"`, add `tests/test_routing_properties.py` covering
   the 20 invariants in §10. 6 already exist in `tests/test_routing_benchmark.py`.
5. **Extra CI workflows** — `.github/workflows/{eval-fast,nightly,security,mutation}.yml`.
6. **500-case benchmark + review workflow** — expand `benchmarks/classifier_gold_v1.yaml` to ≥500
   with paraphrase families; add `agentrouter eval review` (approve/edit/reject/skip → reviewed_gold).
7. **Docs** — `evaluation/{README,DATASETS,METRICS,GRADING,LICENSES,REVIEW_GUIDE}.md`.

## Remaining — need external prerequisites
- **Real dataset runs** (CLINC/BANKING/MASSIVE/LongBench/LLMRouterBench): `pip install -e ".[eval]"`
  then each adapter's `prepare()`/full loader. Each adapter's `full_run_status()` has exact commands.
- **SWE-bench / TwinRouterBench dynamic**: Docker + the official harnesses (SKIPPED_EXTERNAL).
- **Promptfoo**: Node/npm; custom provider calling `agentrouter route "<task>" --json --no-log`.
- **mutmut**: Linux/WSL (needs fork); `pip install -e ".[mutation]" && mutmut run`.
- **Bandit + pip-audit**: `pip install -e ".[security]" && bandit -r agentrouter && pip-audit`.
- **DVC + MLflow**: `pip install -e ".[ops]"`; local file-backed MLflow, `dvc.yaml` stages.

## Resume commands (offline sanity)
```
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest --cov=agentrouter --cov-branch -q
python -m agentrouter eval run --profile nightly --no-artifacts
```
