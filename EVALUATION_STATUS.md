# Evaluation Status

_Canonical status: 2026-07-20._

The offline evaluation framework measures all 100 points and currently scores
**98.32/100** across 165 gold cases. Canonical release readiness is **NO** because
the separately frozen context-band generalization gate fails.

## Frozen context-band study

- Development split: 24 cases, used for the principled classifier revision.
- Final holdout: 45 cases (15 small, 15 medium, 15 large).
- Holdout SHA-256: `ca07dfa09f08cd877d383067b8e1163c0f196a5a1f0c4e641adefed12b17508f`.
- Leakage checks: exact and near-duplicate checks against development, gold, and
  repository test literals.
- Pre-TASK-004 comparator: accuracy 0.4889, macro-F1 0.4453.
- Final current result: accuracy 0.5778 (Wilson 95% CI 0.4330–0.7103), macro-F1
  0.5739 (deterministic bootstrap 95% CI 0.4232–0.6990).
- Per-band recall: small 0.8000, medium 0.2667, large 0.6667.
- Delta from frozen comparator: +0.0889 accuracy, +0.1286 macro-F1.

The classifier was frozen before the one final post-change holdout run. The valid
lower result is retained and was not tuned further. The former 0.945 measurement is
still reported, explicitly as in-sample gold-set context accuracy.

## Canonical command and artifacts

```text
python -m agentrouter eval run --all --out-dir artifacts/evaluation
```

This writes `result.json`, `scorecard.json`, `report.md`, general failures,
confusion matrices, and `context_band_holdout_failures.csv`. The command reports
six passing gates and one failing gate. CI/release enforcement uses
`--require-release-ready` so a failed gate exits nonzero.

## Honest limitations

- The holdout is public and model-assisted, pending independent human review.
- Short prompts infer required context size without supplying real documents.
- Confidence intervals quantify sample uncertainty, not annotation uncertainty.
- External benchmark adapters remain fixture-backed unless their datasets and
  optional infrastructure are explicitly prepared.
