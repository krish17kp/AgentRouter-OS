# AGENT_HANDOFF — live checkpoint

**Canonical volatile handoff.** A fresh session given only "continue from the
previous left-off task" should recover from this file plus the repository and
GitHub state. Detailed history belongs in `LOOP_LOG.md` and the task progress
files, not here.

`CODEX_HANDOFF.md` is a separate, Codex-oriented narrative and is **not**
authoritative for Claude sessions; where the two disagree, this file wins.

---

## Position

| Field | Value |
|---|---|
| Last updated | 2026-08-20 |
| Repository | `/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros` |
| Filesystem | NTFS/fuseblk, verified **rw** this session |
| Active branch | `task/TASK-018-state-reconcile` (state docs only) |
| RC | **`d81ad94`**, post-merge CI **green** (CI, Security, Critical Mutation Testing) |
| `main` | `602321a`, untouched |
| Open PR | none at time of writing. PRs #9, #10, #11 **merged**; their branches deleted |
| Milestone | **EPIC TASK-018 COMPLETE** — all three parts merged |
| Next milestone | **TASK-019** — plugin installer hardening (selected by gap analysis, below) |

## Release truth

**NOT RELEASE READY.** `context_band_accuracy = 0.6667` against the unchanged
`0.90` frozen-holdout gate. The other six gates pass. Only the two-real-human
annotation round in `TASK_012_OWNER_ACTIONS.md` can close it. No AI may act as
Annotator A, Annotator B or adjudicator; the frozen holdout must not be tuned
against; the threshold must not be lowered.

## EPIC TASK-018 — what shipped

**018A** (PR #9, `c11ddec`) — versioned HTTP contract, semantic compatibility
gate, SDK parity. Two review rounds; every finding reproduced then fixed.

**018B** (PR #10, `ff06910`) — reliability lab. **Five real defects**, each
reproduced before being fixed:

1. concurrent routing returned HTTP 500 (`database is locked`) — no WAL, no
   `busy_timeout`; does *not* reproduce through `TestClient`;
2. the WAL fix introduced a silent backup hazard — a plain `cp` of the database
   reports **0 rows, no error**; fixed with `store.snapshot`;
3. an unbounded `task` was a disk-fill primitive (2 MB → 4 MB response + 4 MB
   row) — fixed with bounded request fields, an **owner-approved** breaking
   change recorded in the contract manifest;
4. idempotent POSTs were not idempotent — 12 concurrent same-key requests
   produced **6 decisions**; fixed with per-key single-flight;
5. **CI caught what the dev machine could not** — WAL + 5 s timeout sufficed
   locally, not on slower runners; writers are now serialised in-process.

**018C** (PR #11, `d81ad94`) — unified `agentrouter doctor [--json] [--bundle]`
aggregating the three existing doctors' primitives; secret-safe allowlisted
diagnostic bundle; redaction narrowed so tracebacks keep their paths while 16
credential formats stay masked; correlation-ID tracing asserted end to end
including the error path; twelve runbooks each labelled Verified / Local
procedure / Hypothetical, with a test keeping the citations honest.

The missing **TASK-018A security re-review** was executed and closed —
`loop/tasks/TASK-018B-reliability-load-lab/security-review-018a.md`, no new
critical or high findings.

## Graph

| Field | Value |
|---|---|
| Graphify | **0.9.47** at `~/.venvs/graphify`, linked into `~/.local/bin` |
| Built | 2026-08-20 from RC `d81ad94` |
| Size | **3623 nodes, 7084 edges, 309 communities** |
| Artifacts | `graphify-out/{graph.json,graph.html,GRAPH_REPORT.md}` — local only, gitignored |
| Verified | `save_decision` + four callers checked line-by-line against source |
| Earned its keep | `graphify affected "connect"` exposed the WAL blast radius, which led directly to defect 2 above |
| Community naming | placeholder — labelling needs an LLM backend, deliberately skipped (no paid inference) |

Refresh with `graphify update .` (AST only, no LLM, no API key).

## Latest gates (at `d81ad94`)

| Check | Result |
|---|---|
| pytest | **936 passed, 3 skipped** |
| branch coverage (gate 80%) | **85.42%** |
| ruff check / format | clean, 331 files |
| bandit (`agentrouter` + `scripts`) | 0 issues |
| mutation gate | PASS — 0.986 overall, safety 0.9879, engine 0.9815, 0 unreviewed survivors |
| contract check | unchanged; 8 owner-accepted |

## Next action — TASK-019

```bash
cd "/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros"
findmnt -T "$PWD" -o OPTIONS          # confirm rw first
source "$HOME/.venvs/agentrouter/bin/activate"
export PATH="$HOME/.local/bin:$PATH"
git checkout release/agentrouter-v0.5-rc1 && git pull --ff-only
git checkout -b task/TASK-019-plugin-installer-hardening
```

**Plugin installer hardening.** Chosen by graph-driven gap analysis of the final
RC, not by picking a convenient cleanup. Three signals agree:

1. **Size + coverage** — `agentrouter/plugins.py` is **818 statements at 67.7%**,
   by a wide margin the largest under-tested module (next is
   `evaluation/cli.py` at 129 statements).
2. **Centrality** — four plugin symbols sit in the graph's top 14 hubs:
   `install()` 47 edges, `get_plugin()` 40, `uninstall()` 40, `_dest()` 34.
3. **Blast radius** — it is the only module that writes into directories
   **outside the project** (user agent-config directories) and then removes
   files from them. Its docstring claims it "refuses links/reparse points and
   ambiguous hard links" and "never recursively removes directories" — exactly
   the class of claim 018A/B/C repeatedly found true in intent and incomplete in
   practice, and it has never been adversarially tested.

Approach, as in 018: **reproduce before fixing.** Attack symlink and hardlink
targets, ownership forgery, partial/interrupted installs, concurrent
install+uninstall, a destination that becomes read-only mid-write, path
traversal in a plugin name, and uninstall on a path the user edited. Raise
coverage by killing real defects, never by writing tests that assert current
behaviour.

Full rationale is in `loop/BACKLOG.yaml` under `TASK-019`.

## Open findings

None outstanding. All three findings tracked through this milestone are closed:
the WAL sidecar hazard (fixed via `store.snapshot`), the missing 018A security
re-review (executed, no new critical/high), and the redaction path over-match
(fixed without weakening detection).

## Prohibited

Pushing to `main`; pushing directly to the RC; merging RC → main; force-push;
tags; PyPI/npm publication; deployment; paid inference; lowering any release,
coverage or mutation threshold; weakening tests; fabricating human annotation.
