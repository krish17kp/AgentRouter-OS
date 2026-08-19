# AgentRouter OS — Claude bootstrap

This file loads automatically. It is deliberately short: it points at the
authoritative documents rather than restating them.

**Read `AGENT_HANDOFF.md` first.** It is the live checkpoint — branch, commit, PR,
what is in progress, and the exact next action. A fresh session should be able to
act on "continue from the previous left-off task" using it alone.

@AGENT_HANDOFF.md
@AGENTS.md

`command.md` holds the long-form process spec (phases, gates, guardrails). It is
large, so read it on demand rather than importing it wholesale.

## Non-negotiables

- **Never** push to `main`, push directly to the RC, force-push, tag, publish to
  PyPI/npm, or deploy. Task branches → PR → RC is the only path.
- **Never** lower a release threshold, weaken a test, or allowlist a live mutant
  to obtain a green build.
- The RC is **NOT RELEASE READY** while `context_band_accuracy < 0.90`. It is
  currently **0.6667**. Closing it needs the two-human annotation round in
  `TASK_012_OWNER_ACTIONS.md`; **no AI may act as an annotator or adjudicator**,
  and the frozen holdout must not be tuned against.
- Never print secret values or open credential files.

## Environment

- Repo: `/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros` — the only
  working copy. Never clone, copy, move or recreate it.
- Python: `source "$HOME/.venvs/agentrouter/bin/activate"`
- The repo lives on an **NTFS/fuseblk volume that has remounted read-only before**.
  Before any work: `findmnt -T "$PWD"` and a `touch`/`rm` write test. If it is
  read-only, that is an environment blocker — do not attempt filesystem workarounds.

## Codebase navigation — graph first

Graphify is the navigation layer; executable evidence is the truth layer.

```bash
export PATH="$HOME/.local/bin:$PATH"
graphify update .            # rebuild (AST only, no LLM, no API key)
graphify explain "<symbol>"  # node + neighbours, with file:line
graphify affected "<symbol>" # reverse traversal: blast radius of a change
graphify god-nodes --top 12  # architectural hubs
graphify query "<question>"
```

Visual graph: `graphify-out/graph.html`.

Always verify a graph claim against real source before acting on it. If the graph
and the source disagree, **the source wins** and graph staleness is itself a
finding. Refresh the graph after any architecture-changing commit and after every
merge into the RC.
