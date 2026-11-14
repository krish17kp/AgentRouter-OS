# TASK-009 evidence

Final checksum-locked results:

| measurement | accuracy | macro-F1 | small recall | medium recall | large recall |
|---|---:|---:|---:|---:|---:|
| pre-TASK-004 holdout | 0.4889 | 0.4453 | 0.9333 | 0.0667 | 0.4667 |
| first current holdout | 0.4444 | 0.4141 | 0.8000 | 0.0667 | 0.4667 |
| development after principled revision | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| final current holdout | 0.5778 | 0.5739 | 0.8000 | 0.2667 | 0.6667 |

Final current accuracy 95% Wilson CI: `[0.4330, 0.7103]`.
Final current macro-F1 deterministic bootstrap 95% CI: `[0.4232, 0.6990]`.
Delta versus the frozen historical comparator: accuracy `+0.0889`, macro-F1
`+0.1286`.

The existing `context_band_accuracy>=0.90` gate remains unchanged and **FAILS**.
The other six gates pass and the 100-point grade remains 98.32. Canonical release
readiness is **NO**. This valid lower result is retained; the final holdout was not
tuned further.

Verification:

- `python -m pytest tests/test_context_band.py -q` -> 9 passed.
- focused TASK-009/CLI/report suites -> 20 passed before the final revision.
- `agentrouter eval run --all --json --no-artifacts` -> 7 gates measured, exactly
  the context-band gate failed.
- `python -m agentrouter eval run --all --out-dir artifacts/evaluation` regenerated
  the canonical JSON/Markdown/CSV artifacts on 2026-07-20, including the 19-case
  `context_band_holdout_failures.csv` and dirty-tree/classifier provenance.
- `LOOP_STATE.json`, `loop/QUALITY_GATES.yaml`, `QUALITY_DASHBOARD.md`,
  `RELEASE_READINESS.md`, `PRODUCTION_READINESS.md`, and the root evaluation
  status/acceptance/handoff documents now all report 6/7 gates and readiness NO.
