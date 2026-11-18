# Annotator B — context-band labelling (TASK-012)

You are **Annotator B**. You will independently label all **63** candidate prompts
with a context band (or an abstention), a short rationale, and a confidence. Your
work is **blinded**: you do not see Annotator A's answers, the rule/model
predictions, or the frozen-holdout labels. Do not discuss items with Annotator A
until adjudication.

## What a "context band" means

Judge how much surrounding material a competent responder must hold in context to
do the task **as literally stated** — not the difficulty, not the output length.

- **small (s)** — self-contained; everything needed is in the prompt.
- **medium (m)** — one concrete existing artifact must be read/changed — bounded,
  not a whole corpus.
- **large (l)** — a whole codebase/monorepo, a big document set, or an explicit
  large token/file/page count.
- **abstain (a)** — the context genuinely cannot be inferred from the prompt alone.
  Abstention is a valid, encouraged answer — never guess.

Full guidelines with boundary cases: `docs/CONTEXT_BAND_ANNOTATION.md` §1.

## Setup (once)

```console
pip install -e .
# Your blinded pack (ordering seed 202 is yours; do not use A's seed):
agentrouter dataset pack --annotator B --seed 202 --out packs/pack_B.yaml
```

## Labelling

```console
agentrouter dataset annotate packs/pack_B.yaml --annotator B --out labels/annotator_B.jsonl
```

For each prompt: **band** (`s`/`m`/`l`/`a`), a required one-line **rationale**, and
a **confidence** `0`–`1`.

- Saves after every item — stop with **Ctrl-C** and re-run the same command to
  **resume**; labelled prompts are skipped.
- Records are validated on write; candidate IDs are fixed — never edit them.

## Check progress (counts only, never labels)

```console
agentrouter dataset progress packs/pack_B.yaml --labels labels/annotator_B.jsonl
```

## When done

Label **all 63**, export, and hand `labels/annotator_B.jsonl` to the owner (not to
Annotator A):

```console
agentrouter dataset export labels/annotator_B.jsonl --csv labels/annotator_B.csv
```

## Rules

- Label **every** item independently and honestly. Abstain rather than guess.
- Do **not** look at Annotator A's answers, any model/rule prediction, or the
  frozen holdout.
- Do **not** hand-edit the JSONL. Use the tool.
