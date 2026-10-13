# TASK-012 — owner actions: run the context-band annotation round

This is the one step the software cannot do for you: **two real people must
independently label all 63 candidate prompts.** The tooling prepares blinded packs,
records labels, tracks progress, exports data, and isolates disagreements — but the
final labels must come from humans. Do **not** use any AI/model output as a human
label, and do **not** fabricate labels.

The 63 candidates ship at `agentrouter/benchmarks/context_band/candidates_v1.yaml`
(all ten categories; verified in CI to have zero overlap with the frozen holdout).

## 0. Assign two people

Pick two annotators (A and B) and one adjudicator (can be a third person, or you).
Give each annotator their instruction file and keep them from sharing answers:

- `ANNOTATOR_A_INSTRUCTIONS.md`
- `ANNOTATOR_B_INSTRUCTIONS.md`
- `ADJUDICATOR_INSTRUCTIONS.md`

## 1. Prepare blinded packs (independent orderings)

```console
agentrouter dataset pack --annotator A --seed 101 --out packs/pack_A.yaml
agentrouter dataset pack --annotator B --seed 202 --out packs/pack_B.yaml
```

Different seeds → different orderings. Packs contain only id/prompt/category — no
bands, no predictions, no other annotator's answers.

## 2. Each annotator labels ALL 63, independently

```console
# Annotator A (their machine / session)
agentrouter dataset annotate packs/pack_A.yaml --annotator A --out labels/annotator_A.jsonl
# Annotator B (separately, no shared screen)
agentrouter dataset annotate packs/pack_B.yaml --annotator B --out labels/annotator_B.jsonl
```

Resumable (Ctrl-C then re-run). Each item requires band-or-abstain + rationale +
confidence, validated on write.

Monitor without seeing labels:

```console
agentrouter dataset progress packs/pack_A.yaml --labels labels/annotator_A.jsonl
agentrouter dataset progress packs/pack_B.yaml --labels labels/annotator_B.jsonl
```

Both must reach `63/63` before continuing.

## 3. Adjudicate ONLY disagreements

```console
agentrouter dataset adjudication-pack \
    --labels labels/annotator_A.jsonl \
    --labels labels/annotator_B.jsonl \
    --out packs/adjudication.yaml
```

Give `packs/adjudication.yaml` + `ADJUDICATOR_INSTRUCTIONS.md` to the adjudicator.
They return `adjudications.json`. There is no auto-adjudication.

## 4. Build the versioned, leakage-checked dataset

```console
agentrouter dataset build \
    --labels labels/annotator_A.jsonl \
    --labels labels/annotator_B.jsonl \
    --adjudications adjudications.json \
    --out-dir datasets/context_band --version v2.0.0
```

This merges labels, applies your adjudications, refuses any dev/holdout item that
leaks the frozen holdout, writes `context_band_{train,dev,holdout}_v2.0.0.yaml`, a
`manifest_v2.0.0.json` (per-split SHA + provenance), and a `leakage_report.json`.

## 5. Compare, then evaluate the private holdout ONCE

```console
# rules vs learned vs hybrid on the NEW dev split (never the frozen holdout)
agentrouter dataset compare datasets/context_band/context_band_dev_v2.0.0.yaml --out compare.json
```

Then evaluate the **new private holdout at most once per candidate model**. Record
the honest number even if it is still below 0.90. Do **not** tune against it, do
**not** reuse the frozen holdout, and do **not** change the 0.90 gate.

## Guardrails (must hold)

- Two real, independent human annotators label all 63; abstention is allowed.
- No AI-generated label is used as a human label; no fabricated labels.
- The frozen TASK-009 holdout is never reused or tuned against (only leakage-checked).
- The 0.90 release gate is unchanged; the RC stays NOT RELEASE READY until real
  labels close the gap honestly.

## Optional: CSV export for offline review

```console
agentrouter dataset export labels/annotator_A.jsonl --csv labels/annotator_A.csv
agentrouter dataset export labels/annotator_B.jsonl --csv labels/annotator_B.csv
```
