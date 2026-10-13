# TASK-011 — Context-band data and annotation program

## Why

The v0.5 release gate `context_band_accuracy >= 0.90` is the single honest
blocker. TASK-009 proved the 24-case development set is a ceiling: on the frozen
holdout, rules score 0.6667, learned 0.6889, hybrid 0.6444 — none reach 0.90 and
the learned model is not significantly better than rules (overlapping CIs, lower
macro-F1). More hand-rules cannot close this; the data is the limit.

The objective is a **substantially larger human-reviewed development dataset and a
new private holdout**, built to measure honest generalization — not to force the
old score up.

## Guardrails (non-negotiable)

- Do **not** reuse or tune against the current frozen TASK-009 holdout.
- Diverse/LLM prompt generation is for **candidate collection only**. A human
  reviewer assigns every final label.
- No threshold changes. Record the true result even if still below 0.90.

## Phases

### P1 — Annotation guidelines + schema
- Written small/medium/large definitions with boundary cases and worked examples.
- Item schema: `prompt`, `band`, `label_source` (candidate origin), `annotators`,
  `adjudicated_by`, `provenance`, `split`, dataset `version`.
- Abstention/uncertainty band for genuinely ambiguous one-line prompts.

### P2 — Labeling interface (CLI first)
- A CLI (`agentrouter eval context-band annotate` or a standalone script) that
  presents a candidate prompt, records per-annotator labels, flags disagreement,
  and routes ties to an adjudication queue. Reuse existing Typer CLI patterns.
- Ladder note: CLI over any web UI unless annotators actually need one.

### P3 — Candidate collection (no auto-labels)
- Gather diverse candidates: real developer prompts, varied vocabulary/syntax,
  adversarial near-neighbors, short ambiguous prompts. LLM-generated candidates
  allowed **only** as unlabeled input to human review.
- Optional: enrich with Graphify repository/file-impact signals (affected node
  count, dependency reach) as features — must degrade gracefully when absent.

### P4 — Split + leakage control
- Strict train / dev / private-holdout separation.
- Exact + near-duplicate (normalized + embedding/shingle) leakage detection across
  splits and against existing gold/test literals. Report and remove duplicates.

### P5 — Modeling comparison
- Compare rules vs learned vs hybrid on the new dev set: accuracy, macro-F1,
  per-band recall, confidence intervals, abstention behavior.
- Reproducible training from a pinned command; versioned dataset artifacts.

### P6 — Single honest holdout evaluation
- Evaluate at most once per candidate model against the new private holdout.
- Record the honest number. If still < 0.90, document the remaining gap and next
  data investment — do not tune, reduce the gate, or touch the frozen holdout.

## Evidence to produce
- Versioned dataset files + provenance manifest.
- Guidelines + adjudication protocol docs.
- Leakage report.
- Comparison report (rules/learned/hybrid) with CIs.
- Honest holdout result + limitations.

## Open questions for owner
- Source(s) of real developer prompts (privacy/consent).
- Annotator pool + how many labels per item / adjudication authority.
