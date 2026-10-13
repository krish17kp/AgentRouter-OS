# Annotator A — context-band labelling (TASK-012)

You are **Annotator A**. You will independently label all **63** candidate prompts
with a context band (or an abstention), a short rationale, and a confidence. Your
work is **blinded**: you do not see Annotator B's answers, the rule/model
predictions, or the frozen-holdout labels. Do not discuss items with Annotator B
until adjudication.

## What a "context band" means

Judge how much surrounding material a competent responder must hold in context to
do the task **as literally stated** — not the difficulty, not the output length.

- **small (s)** — self-contained; everything needed is in the prompt (a fresh
  snippet, a definition, a conceptual question).
- **medium (m)** — one concrete existing artifact must be read/changed (a module,
  a patch, a handbook, a feed) — bounded, not a whole corpus.
- **large (l)** — a whole codebase/monorepo, a big document set, or an explicit
  large token/file/page count.
- **abstain (a)** — the context genuinely cannot be inferred from the prompt alone
  (e.g. "Make this nicer."). Abstention is a valid, encouraged answer — never guess.

Full guidelines with boundary cases: `docs/CONTEXT_BAND_ANNOTATION.md` §1.

## Setup (once)

```console
pip install -e .
# Your blinded pack (ordering seed 101 is yours; do not use B's seed):
agentrouter dataset pack --annotator A --seed 101 --out packs/pack_A.yaml
```

## Labelling

```console
agentrouter dataset annotate packs/pack_A.yaml --annotator A --out labels/annotator_A.jsonl
```

For each prompt you will be asked for:
1. **band** — type `s`, `m`, `l`, or `a` (abstain);
2. **rationale** — one line on *why* (required);
3. **confidence** — a number `0`–`1`.

- The tool **saves after every item**, so you can stop any time with **Ctrl-C**
  and simply re-run the same command to **resume** — already-labelled prompts are
  skipped.
- Every record is validated on write; an invalid band is rejected and re-asked.
- Candidate IDs are fixed — never edit them.

## Check progress (reveals counts only, never labels)

```console
agentrouter dataset progress packs/pack_A.yaml --labels labels/annotator_A.jsonl
```

## When done

You must have labelled **all 63**. Export a copy and hand `labels/annotator_A.jsonl`
to the owner (not to Annotator B):

```console
agentrouter dataset export labels/annotator_A.jsonl --csv labels/annotator_A.csv
```

## Rules

- Label **every** item independently and honestly. Abstain rather than guess.
- Do **not** look at Annotator B's answers, any model/rule prediction, or the
  frozen holdout.
- Do **not** hand-edit the JSONL. Use the tool.
