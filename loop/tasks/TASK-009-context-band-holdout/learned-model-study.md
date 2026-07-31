# TASK-009 — Learned context-band classifier study (decision A)

**Date:** 2026-07-31
**Question:** Can a small, explainable, dev-only learned model reach the frozen
0.90 context-band holdout gate where hand-rules plateaued at 0.6667?
**Answer:** No. A documented technical ceiling: 24 development cases cannot
generalize to 0.90 on the 45-case frozen holdout by any of rules / learned /
hybrid. Ship rules-active; retain the learned model as a tested, packaged artifact.

## Method (graph-aware production loop)

- **Data audit / leakage:** dev (24, 8/8/8) vs frozen holdout (45, 15/15/15),
  SHA-pinned. Cross-split exact + near-duplicate check (normalized prompt
  similarity) — no leakage. Holdout never used for fit or model selection.
- **Model:** multinomial logistic regression (sklearn, **dev-time only**) over 14
  interpretable regex features. Runtime inference is **pure Python** (softmax over
  JSON-exported weights) — no sklearn, no network, deterministic.
  - Feature extractor is the single source of truth (`agentrouter/context_model.py`),
    shared by training and runtime, so train/serve skew is impossible.
- **Selection:** LeaveOneOut CV on dev only (LOOCV 0.9583, train acc 1.0), C=1.0
  fixed a priori. Artifact: `agentrouter/benchmarks/context_band_model_v1.json`.
- **Holdout:** evaluated **exactly once**, across all three configs together. The
  shipped config was fixed before this run.

## Result — frozen 45-case holdout (evaluated once)

| config | accuracy | 95% CI | macro-F1 | recall S / M / L |
|--------|:--------:|:------:|:--------:|:----------------:|
| **rules-only (SHIPPED)** | **0.6667** | [0.521, 0.786] | **0.6792** | 0.733 / **0.600** / 0.667 |
| learned-only | 0.6889 | [0.543, 0.805] | 0.6613 | 0.800 / 0.333 / 0.933 |
| hybrid (0.45 conf.) | 0.6444 | [0.498, 0.768] | 0.6188 | 0.667 / 0.333 / 0.933 |

All three dev = 1.0000 (overfit-perfect on 24 cases, as expected).

## Findings

1. **No config reaches 0.90.** Best (learned-only 0.6889) misses by >0.21; its CI
   lower bound is 0.543. The gap is structural, not tuning.
2. **Learned is not significantly better than rules.** +0.0222 accuracy with
   near-identical, heavily overlapping CIs.
3. **Learned trades balance for large recall.** It lifts large recall 0.667→0.933
   but **collapses medium recall 0.600→0.333**, so its macro-F1 is *lower* than
   rules (0.6613 < 0.6792). Hybrid inherits the collapse and is worst overall.
4. **Ceiling cause:** band labels infer required input size from short prompts with
   no real files. 24 dev cases underdetermine the medium/large boundary; the model
   latches onto explicit token cues (helping large) at medium's expense.

## Decision

Ship **rules-active** (`_USE_LEARNED_BAND = False` in `agentrouter/classifier.py`):
best macro-F1, balanced per-band recall, no significant accuracy loss, fully
explainable. The learned model stays in the wheel as a tested artifact behind the
flag, with a pure-Python loader that falls back to rules on any error and a
confidence threshold for future hybrid use — no runtime cost while disabled.

**Honest gate state:** context_band_accuracy 0.6667 < 0.90 → gate **FAIL** (6/7
gates pass, grade 98.23). This is a proven ceiling for the current dataset, not a
defect. Raising it honestly requires a larger, human-labeled development set (or
real-file context signals), not more hand-rules or holdout-driven tuning.

**Independent audit (2026-07-31):** release-auditor reproduced all three configs,
the 6/7 gate split, grade 98.23, and the packaged-wheel load; verified the 0.90
threshold and frozen holdout (sha256 `ca07dfa…`) are untouched. Verdict:
FAIL-to-release / correctly HELD — a real, reproduced dataset ceiling, safe to hold
unpushed pending owner authorization. security-reviewer-arros: no CRITICAL/HIGH; one
LOW (load_model missing `TypeError` in its except tuple) fixed + regression-tested.

**Not pushed / not released** — a mandatory gate is failing; owner authorization
required to push the RC with a failing gate.

## Artifacts

- `agentrouter/context_model.py` — features + pure-Python LR inference (leaf module).
- `agentrouter/benchmarks/context_band_model_v1.json` — dev-trained weights (packaged).
- `tests/test_context_model.py` — 7 tests (load, predict, shape, rules-active default,
  explicit-token override, missing-model fallback, malformed-model → None contract).
- Clean-wheel verified: JSON packaged, loads from a fresh `pip install`.
