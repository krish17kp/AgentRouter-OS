# Evaluation Status

_Originally canonical 2026-07-20; the context-band numbers below are SUPERSEDED by
TASK-009's decision-A holdout run (2026-07-31) and unchanged since. Current
canonical figures live in `RELEASE_READINESS.md`, `QUALITY_DASHBOARD.md`, and
`LOOP_STATE.json` — accuracy **0.6667** (rules-active), macro-F1 **0.6792**,
per-band recall small/medium/large **0.733/0.600/0.667**. This file's numbers
below are retained as history, not current evidence._

The offline evaluation framework measures all 100 points and currently scores
**98.23/100** (updated post-TASK-009; was 98.32) across 165 gold cases. Canonical
release readiness is **NO** because the separately frozen context-band
generalization gate fails (0.6667 < 0.90, unchanged threshold).

## Frozen context-band study (superseded numbers — see banner above)

- Development split: 24 cases, used for the principled classifier revision.
- Final holdout: 45 cases (15 small, 15 medium, 15 large).
- Holdout SHA-256: `ca07dfa09f08cd877d383067b8e1163c0f196a5a1f0c4e641adefed12b17508f`.
- Leakage checks: exact and near-duplicate checks against development, gold, and
  repository test literals.
- Pre-TASK-004 comparator: accuracy 0.4889, macro-F1 0.4453.
- Result as of 2026-07-20 (pre-TASK-009): accuracy 0.5778 (Wilson 95% CI
  0.4330–0.7103), macro-F1 0.5739 (deterministic bootstrap 95% CI 0.4232–0.6990),
  per-band recall small 0.8000, medium 0.2667, large 0.6667.
- **Current (post-TASK-009, 2026-07-31, unchanged since):** accuracy 0.6667,
  macro-F1 0.6792, per-band recall small/medium/large 0.733/0.600/0.667. TASK-009
  additionally tested a dev-only learned classifier (0.6889 acc / 0.6613 macro-F1)
  and a hybrid (0.6444 / 0.6188) — neither reaches 0.90 nor is significantly
  better than rules, so rules-active shipped. See
  `loop/tasks/TASK-009-context-band-holdout/learned-model-study.md`.

The classifier was frozen before each final post-change holdout run; no holdout
tuning occurred at any point. The former 0.945 measurement is still reported,
explicitly as in-sample gold-set context accuracy, not held-out generalization.

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
