# TASK-011 progress

Branch: `task/TASK-011-context-band-data` (from `release/agentrouter-v0.5-rc1`).
Status: **system built + tested**; final human-reviewed labels are the remaining
external step.

## Delivered (this iteration)

- `agentrouter/annotation/` package (leaf; imports classifier/context_model/eval
  read-only — no edits to rules, learned runtime, frozen holdout, or the gate):
  - `schema.py` — typed contract (Candidate, AnnotatorLabel, ItemLabels,
    AdjudicatedItem, DatasetManifest); band **xor** abstain; rationale+confidence
    required on every label; provenance + split + review_status.
  - `candidates.py` — deterministic, **unlabelled** generator across all ten
    categories at three implied scopes; unique prompts only.
  - `dedup.py` — normalise + exact + sensitive near-dup (max of shingle-Jaccard
    and edit-ratio, threshold 0.8); union-find clustering; cross-set leakage.
  - `adjudicate.py` — two-annotator merge; agreement / unanimous-abstention /
    disagreement→adjudicator; never fabricates a band.
  - `splits.py` — deterministic, cluster-aware train/dev/holdout; refuses any
    dev/holdout leak against the frozen holdout (`LeakageError`).
  - `compare.py` — rules/learned/hybrid: accuracy, macro-F1, per-band recall,
    bootstrap CI, ECE calibration, rules-fallback/abstention rates.
  - `graph_signals.py` — optional Graphify repo-impact feature; text-only fallback.
  - `store.py` — YAML/JSONL I/O + SHA-stable versioned manifest.
  - `cli.py` — `agentrouter dataset {gen-candidates,annotate,build,compare,leakage}`.
- Shipped artifact: `agentrouter/benchmarks/context_band/candidates_v1.yaml`
  (63 unique candidates, all 10 categories, **0 leaks** vs the frozen holdout —
  CI-guarded).
- Docs: `docs/CONTEXT_BAND_ANNOTATION.md` (S/M/L guidelines + boundary cases,
  item schema, adjudication protocol, splits/leakage, reproducible commands,
  honest-limitations note).
- Tests: `tests/test_annotation.py` + `tests/test_annotation_cli.py` (25 tests):
  schema, dedup/leakage, generation determinism + full-category coverage,
  committed-pool isolation, **frozen-holdout SHA unchanged**, adjudication,
  leakage-safe splits, comparison metrics, graph fallback, and the CLI pipeline.

## Guardrails honoured

- Frozen TASK-009 holdout untouched (SHA asserted in a test); only leakage-checked.
- Generated prompts are candidates only; no automatic final labels.
- 0.90 gate unchanged; RC stays NOT RELEASE READY.

## Remaining (external / next)

- Real two-annotator human labelling of the candidate pool + adjudication → the
  materially-larger human-reviewed dev set and the new private holdout.
- Single honest holdout evaluation per candidate model once real labels exist.
