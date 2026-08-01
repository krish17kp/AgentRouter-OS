# Adjudicator — resolving context-band disagreements (TASK-012)

You are the **adjudicator**. After both annotators finish independently, you decide
the final band for **only** the items where they disagreed. You never see the
model/rule predictions or the frozen holdout, and there is **no auto-adjudication**
— every disagreed item is decided by you, a human.

## Build the disagreements-only pack

The owner runs (or gives you the output of):

```console
agentrouter dataset adjudication-pack \
    --labels labels/annotator_A.jsonl \
    --labels labels/annotator_B.jsonl \
    --out packs/adjudication.yaml
```

`packs/adjudication.yaml` is **blinded**: it contains only the disputed prompts
(id, prompt, category) — not the two annotators' bands. Decide each on its merits
using the same guidelines the annotators used (`docs/CONTEXT_BAND_ANNOTATION.md` §1).

An item also appears here if only one annotator labelled it — that means the second
label is missing; treat it as needing your decision.

## Record decisions

Label the adjudication pack exactly like an annotator, using your own id:

```console
agentrouter dataset annotate packs/adjudication.yaml \
    --annotator adjudicator --out labels/adjudicator.jsonl
```

Then convert your decisions into the build's adjudication format — a JSON array,
one object per disputed candidate:

```json
[
  {
    "candidate_id": "cand-0007",
    "adjudicator": "your-name",
    "band": "medium",
    "abstain": false,
    "rationale": "names one existing component; bounded to that module",
    "confidence": 0.7
  }
]
```

- Use `"abstain": true` (and omit `band`) if the prompt genuinely cannot be judged.
- One entry per disputed `candidate_id`; do not add entries for items that agreed.

Hand `adjudications.json` to the owner for the final `build`.

## Rules

- Decide **only** disputed items; agreements stand as-is.
- Never fabricate a decision to "break a tie" — abstain if the prompt is truly
  ambiguous.
- Never consult a model/rule prediction or the frozen holdout.
