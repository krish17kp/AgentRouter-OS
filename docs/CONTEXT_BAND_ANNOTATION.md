# Context-band data & annotation program (TASK-011)

A local, offline program for building a **human-reviewed** context-band dataset
and a **fresh private holdout** for small / medium / large classification — the
honest path to the `context_band_accuracy >= 0.90` release gate that TASK-009
proved the 24-case set could not reach.

> **Guardrails (non-negotiable).** The frozen TASK-009 holdout
> (`agentrouter/benchmarks/context_band_holdout_v1.yaml`, SHA-pinned) is **never
> reused or tuned against**. Generated prompts are **candidates only** — a human
> assigns every final label. The 0.90 gate is **never** lowered. Honest results
> are recorded even if still below 0.90.

## 1. Band definitions (annotation guidelines)

The band is the amount of surrounding material a competent responder must hold in
context to do the task **as literally stated** — not the difficulty, not the
output length.

### small
Self-contained. The prompt carries everything needed; no external file, codebase,
or document must be read. Typically a fresh snippet, a definition, or a
conceptual question.
- *"Produce a helper that rounds a timestamp down to the nearest minute."*
- *"At a high level, contrast polling with webhooks."*

### medium
Bounded existing artifact. The task references **one** concrete, already-existing
thing (a module, component, patch, handbook, feed) that must be understood or
changed, but not a whole corpus.
- *"Rework the alerts module so its outward behavior stays identical."*
- *"Collapse the current on-call playbook into a single printable page."*

### large
Broad corpus or large token budget. The task spans a whole codebase/monorepo, a
big document set, or an explicit large token/file/page count.
- *"Comb 140k tokens of gateway access logs for anomalous session behavior."*
- *"Reorganize a checked-out tree of roughly twelve hundred modules for clarity."*

### Boundary cases
- **A named component vs. "the system"** → one component is *medium*; the whole
  system/monorepo is *large*.
- **Explicit token/page/file counts** → thresholds win: tens of k tokens or
  hundreds of files/pages is *large*; a single file/page is *small*/*medium*.
- **Ambiguous one-liners** ("Have a look.", "Make this nicer.") → often *abstain*:
  the context genuinely cannot be inferred from the prompt alone. Abstention is a
  first-class outcome, not a failure.

## 2. Item schema

Each dataset item (`agentrouter/annotation/schema.py :: AdjudicatedItem`):

| field | meaning |
|---|---|
| `id`, `prompt`, `category` | identity + one of the ten categories |
| `band` / `abstained` | final label — a band **or** an explicit abstention |
| `label_source` | provenance of the *candidate* (`generated_candidate`/`curated`/`real_prompt`) |
| `annotators` | ids of the annotators who labelled it |
| `adjudicated_by` | set **only** when annotators disagreed |
| `rationale`, `confidence` | recorded with **every** label |
| `split` | `train` / `dev` / `holdout` |
| `review_status` | `pending_human_review` until a human signs off |

Categories: coding, review, refactor, documentation, summarization, analysis,
data-pipeline, rag, tool-use, ambiguous.

## 3. Adjudication protocol

Two annotators label independently, each recording band (or abstain), a one-line
rationale, and a 0–1 confidence.

- **Agreement** (all non-abstaining annotators pick the same band) → accepted; no
  adjudicator; confidence = mean of annotator confidences.
- **Unanimous abstention** → recorded as an abstained item.
- **Disagreement** (different bands, or abstain-vs-band) → routed to a third
  **adjudicator** who records the deciding band and rationale. The item is
  **never** auto-resolved; `build` refuses (exit 2) until every disagreement has
  an adjudication decision.

## 4. Splits & leakage control

- `train : dev : holdout = 0.60 : 0.25 : 0.15`, assigned deterministically by
  hashing each near-duplicate **cluster** (so a prompt and its near-twin never
  straddle a split).
- Near-duplicate = normalised-exact **or** similarity ≥ 0.8, where similarity is
  the max of word-shingle Jaccard and a normalised edit ratio (a deliberately
  *sensitive* guard).
- `build` refuses to place any dev/holdout item that exact- or near-duplicates a
  frozen-holdout prompt, and writes a `leakage_report.json`. Checking against the
  frozen holdout is a **leakage guard**, not tuning — no frozen label is read.

## 5. Reproducible commands

```console
# 1. generate an UNLABELLED candidate pool (deterministic)
agentrouter dataset gen-candidates --out candidates.yaml

# 2. two annotators label independently (interactive)
agentrouter dataset annotate candidates.yaml --annotator alice --out alice.jsonl
agentrouter dataset annotate candidates.yaml --annotator bob   --out bob.jsonl

# 3. (adjudicate disagreements -> adjudications.json), then build splits + manifest
agentrouter dataset build --labels alice.jsonl --labels bob.jsonl \
    --adjudications adjudications.json --out-dir datasets/context_band --version v2.0.0

# 4. compare rules / learned / hybrid on the NEW dev split (never the holdout)
agentrouter dataset compare datasets/context_band/context_band_dev_v2.0.0.yaml --out compare.json

# 5. prove the new holdout does not leak the frozen holdout
agentrouter dataset leakage datasets/context_band/context_band_holdout_v2.0.0.yaml
```

The shipped candidate pool (`agentrouter/benchmarks/context_band/candidates_v1.yaml`,
63 unique prompts across all ten categories) is regenerated by step 1 and is
verified in CI to contain **zero** leaks against the frozen holdout.

## 6. Modeling comparison

`agentrouter dataset compare` evaluates three strategies on the new dev split:
- **rules** — the shipped rule-based band estimator;
- **learned** — the packaged logistic model (`context_model.py`);
- **hybrid** — learned when confident, else rules.

Reported per strategy: accuracy, macro-F1, per-band recall, a bootstrap 95% CI for
accuracy, expected calibration error (ECE), and the rules-fallback / abstention
rates. Abstained items are excluded from accuracy and reported separately.

## 7. Optional repository-impact signal

When a Graphify `graph.json` is present, `graph_signals.impact_for(prompt)` returns
a bounded impact score from the affected dependency neighbourhood of any
repository artifacts the prompt names. It **degrades gracefully** to a text-only
fallback (`feature = 0.0`) when the graph is absent — AgentRouter never depends on
Graphify for basic operation.

## 8. Status & honest limitations

This delivers the full **system** (schema, generation, annotation CLI, two-annotator
adjudication, dedup/leakage, leakage-safe splits, versioned manifests, and the
comparison harness) plus a verified unlabelled candidate pool. Producing the
**final human-reviewed labels** requires annotator time and is the remaining
external step; every generated label is flagged `pending_human_review` until then.
The 0.90 gate remains unchanged and the release branch stays **NOT RELEASE READY**.
