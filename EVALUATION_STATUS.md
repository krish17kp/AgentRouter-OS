# EVALUATION_STATUS

Live status of the evaluation program. Statuses: `[x]` done+verified · `[~]` implemented, external/full run pending · `[ ]` incomplete, locally actionable.

- **Repo SHA at start:** 67548a2 · **Python:** 3.13.7 · pydantic 2.13.4 · typer 0.26.8
- **Baseline (classifier, pre-change):** measured-grade 93.2/100, high-risk recall 1.00, context-band gate FAILS (0.76 < 0.90)
- **Baseline artifacts:** `artifacts/evaluation/baseline_v0.4.0.{json,md}`, `baseline_failures_v0.4.0.csv`
- **Test suite:** 264 passed (165 pre-existing + 99 new eval), coverage 86.92%+ (branch), ruff clean.

## Real dataset preparation (command.md Assignment A) — DONE

Real/fixture source axis added: `load(source="fixture"|"real")`, `sample(..., source=...)`, no silent
fallback (real failure → `SkippedExternal`). CLI: `eval prepare --dataset/--all`, `eval status`,
`eval run --source real|fixture`. HF cache root `data/huggingface` (gitignored). `datasets` pinned <4.

Real smoke (HF_HOME=data/huggingface), records downloaded / evaluated:

| dataset | source repo | revision | license | downloaded | sampled | status |
|---|---|---|---|---|---|---|
| banking77 | PolyAI/banking77 | latest | MIT | 3079 | 5 | REAL ✅ |
| massive | AmazonScience/massive | latest | CC BY 4.0 | 8843 (en/hi/fr) | 5 | REAL ✅ |
| longbench-v2 | THUDM/LongBench-v2 | latest | dataset card | 488 | 5 | REAL ✅ |
| swebench | princeton-nlp/SWE-bench_Lite | latest | MIT+repo | 300 (metadata) | 5 | REAL ✅ (no Docker) |
| clinc150 | clinc_oos | — | CC BY 3.0 | — | — | SKIPPED_EXTERNAL |
| llmrouterbench | (unverified) | — | — | — | — | SKIPPED_EXTERNAL |
| twinrouterbench | (unverified) | — | — | — | — | SKIPPED_EXTERNAL |

Exact blockers: **clinc150** — `clinc_oos` loader script emits `hf://` URIs rejected by `datasets>=3`
(`HfUriError`); fixture mode works. **llmrouterbench / twinrouterbench** — no official HF repo verified,
so real loader is intentionally not configured (would be inventing a source); fixture + SKIPPED honest.
End-to-end `eval run --dataset banking77 --source real --limit 50` → measured grade 68.6 (real customer
queries classify variously — honest signal, not the curated-gold 93).

## Phase progress

| Phase | Item | Status | Evidence |
|-------|------|--------|----------|
| 2 | Evaluation package architecture | [x] | `agentrouter/evaluation/` (schema, base, sampling, provenance, registry, metrics, grading, reports, comparison, runner, cli, adapters/) |
| 3 | Common EvaluationCase schema + validation | [x] | `evaluation/schema.py`, `tests/evaluation/test_eval_schema.py` |
| 4 | AgentRouter benchmark (≥500) | [~] | reuses `benchmarks/classifier_gold_v1.yaml` (165 human cases). 500-case expansion + paraphrase families + review workflow PENDING |
| 5.1 | AgentRouter gold adapter | [x] | `adapters/agentrouter_gold.py` + test (READY, 165 cases) |
| 5.2 | LLMRouterBench adapter | [~] | fixture-tested (6); full run SKIPPED_EXTERNAL (`full_run_status()`) |
| 5.3 | TwinRouterBench adapter | [~] | fixture-tested (6, static track); dynamic SKIPPED_EXTERNAL (Docker) |
| 5.4 | SWE-bench adapter | [~] | fixture-tested (6); full run SKIPPED_EXTERNAL (Docker) |
| 5.5 | LongBench v2 adapter | [~] | fixture-tested (8, 5 buckets); full SKIPPED_EXTERNAL |
| 5.6 | CLINC150 adapter | [~] | fixture-tested (12, incl. out-of-scope); full run needs `datasets` |
| 5.7 | BANKING77 adapter | [~] | fixture-tested (12, risk-calibration contrasts verified); full run needs `datasets` |
| 5.8 | MASSIVE adapter | [~] | fixture-tested (12, en/hi/fr; language filter verified) |
| 6.1 | Classification metrics (30pt) | [x] | `metrics.py` (acc, macro-F1, per-class, confusion, tool micro-F1, high-risk recall) |
| 6.2 | Routing metrics (25pt) | [ ] | dimension declared **pending** in scorecard; evaluator not built |
| 6.3 | Safety metrics (15pt) | [ ] | pending (existing `tests/test_execute_injection.py` covers injection separately) |
| 6.4–6.7 | CLI/provider/feedback/perf metrics | [ ] | pending dimensions in scorecard |
| 7 | 100-point grade + release gates | [~] | `grading.py`: classification measured; other 70pts honestly reported as pending (never rescaled away) |
| 8 | Baseline capture | [x] | `artifacts/evaluation/baseline_v0.4.0.*` |
| 9 | Classifier improvement (post-baseline) | [ ] | not started (framework-first) |
| 10 | Routing invariants (Hypothesis, 20) | [~] | 6 invariants live in `tests/test_routing_benchmark.py`; Hypothesis + remaining 14 pending |
| 11.1 | pytest markers | [x] | `pyproject.toml [tool.pytest.ini_options].markers` |
| 11.2 | branch coverage | [x] | on; xml/json/html report flags documented in §18 |
| 11.3 | Ruff | [x] | green across new code |
| 11.4 | GitHub Actions (fast/nightly/security/mutation) | [ ] | only base CI exists |
| 11.5 | Hypothesis | [ ] | extra declared; property tests pending |
| 11.6 | Promptfoo | [ ] | pending |
| 11.7 | mutmut | [ ] | pending |
| 11.8 | Bandit + pip-audit + secret scan | [ ] | extras declared; jobs pending |
| 11.9 | pytest-benchmark | [ ] | extra declared; benchmarks pending |
| 11.10 | DVC + MLflow | [ ] | extras declared; config pending |
| 15 | Reports (json/md/csv/confusion/scorecard) | [x] | `reports.py` + comparison; verified via CLI |
| 16 | Documentation | [~] | this file + ACCEPTANCE + HANDOFF; evaluation/*.md pending |
| 17 | Optional dependency extras | [x] | `pyproject.toml` eval/property/security/benchmark/mutation/ops/all-eval |

## What runs today (offline, no keys)
```
python -m agentrouter eval list-datasets
python -m agentrouter eval validate-dataset agentrouter-gold
python -m agentrouter eval run --profile fast
python -m agentrouter eval run --profile nightly            # gold+clinc+banking+massive fixtures
python -m agentrouter eval run --dataset massive --languages en,hi
python -m agentrouter eval report artifacts/evaluation/current/result.json
python -m agentrouter eval compare <baseline.json> <current.json>
```

## Honest limitations
- Only the **classification** dimension (30/100) is measured. Routing/safety/CLI/provider/feedback/perf are declared **pending** and count as 0 in `grade_over_100` — the headline grade is deliberately NOT rescaled to hide unbuilt work. `grade_of_measured` shows the classification-only number (93.2).
- All 7 non-gold adapters run from small **model-assisted synthetic fixtures**, not the real datasets. Full runs are `SKIPPED_EXTERNAL` with exact commands in each adapter's `full_run_status()`.
- The 500-case benchmark, human-review workflow, Promptfoo, mutmut, Bandit, DVC/MLflow, and the extra CI workflows are **not built** — see `EVALUATION_HANDOFF.md`.
- Git policy honored: no add/commit/push/tag/PR.
