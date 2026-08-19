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
| Last updated | 2026-08-19 |
| Repository | `/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros` |
| Filesystem | NTFS/fuseblk, verified **rw** this session |
| Active branch | `task/TASK-018B-reliability-load-lab` |
| Current commit | `0db82cd` (**local only — not pushed**) |
| Remote branch | none yet for TASK-018B |
| RC | `release/agentrouter-v0.5-rc1` @ `c11ddec`, post-merge CI **green** (CI, Security, Critical Mutation Testing) |
| `main` | `602321a`, untouched |
| Open PR | none. PR #9 (TASK-018A) **merged**; its branch deleted local + remote |
| Milestone | EPIC TASK-018 — production reliability & operational resilience |
| Phase | TASK-018B (reliability/load lab) in progress |

## Release truth

**NOT RELEASE READY.** `context_band_accuracy = 0.6667` against the unchanged
`0.90` frozen-holdout gate. The other six gates pass. Only the two-real-human
annotation round in `TASK_012_OWNER_ACTIONS.md` can close it. No AI may act as
Annotator A, Annotator B or adjudicator; the frozen holdout must not be tuned
against; the threshold must not be lowered.

## Completed

- **TASK-018A** — versioned HTTP contract, semantic compatibility gate, SDK
  parity. Merged via PR #9 (`c11ddec`). Two independent review rounds; every
  finding reproduced then fixed. See `loop/tasks/TASK-018A-*/progress.md`.
- **TASK-018B, first defect** — 200 concurrent `POST /v1/route` against a real
  uvicorn server returned **3 × HTTP 500** (`sqlite3.OperationalError: database
  is locked`) from `store.save_decision`. Root cause: `store.connect()` had no
  `journal_mode=WAL` and no `busy_timeout` (SQLite's default is 0, so the first
  contended write fails outright), and it re-ran the schema script on every
  connection while the server opens one per request. Fixed in `0db82cd`:
  200/200 OK, zero lost writes, p95 4539 ms → 2630 ms.
  Tests were verified to have teeth — reverting only the two PRAGMA lines makes
  two of them fail with the original error.

## In progress / open findings

1. **WAL sidecar hazard (new, caused by the 018B fix).** With a WAL active,
   copying only `agentrouter.db` produces a database with **no tables at all**
   (`no such table: decisions`) — total data loss for a naive backup or
   diagnostic bundle. Needs a WAL-safe snapshot helper in `store.py`, a test, and
   it must be what TASK-018C's diagnostic bundle uses. **Not yet implemented.**
2. **TASK-018A security re-review never returned** — the previous session hit a
   usage limit. The 018A security fixes have regression tests, but no fresh
   adversarial pass has covered the merged diff. Must be closed before the
   milestone is called done.
3. **Redaction over-matches file paths.** The widened `observability._SECRET_RE`
   matches long `[A-Za-z0-9+/]{40,}` runs, so traceback paths render as
   `04 - Dev [redacted].py`. Safe direction, but it costs diagnosability. Fix in
   TASK-018C **without weakening secret redaction**.

## Graph

| Field | Value |
|---|---|
| Graphify | **0.9.47**, installed at `~/.venvs/graphify`, linked into `~/.local/bin` |
| Built | 2026-08-19 from working tree at `0db82cd` |
| Size | 3375 nodes, 6650 edges, 277 communities |
| Artifacts | `graphify-out/graph.json`, `graph.html`, `GRAPH_REPORT.md` (all non-empty) |
| Verified | `save_decision` node and its four callers checked line-by-line against source — all correct |
| Hubs | `classify()`, `diff_contracts()`, `detect_host()`, `create_app()`, `ModelEntry`, `EvaluationCase` |
| Community naming | placeholder ("Community N") — labelling needs an LLM backend and is deliberately skipped (no paid inference) |

`store.connect()` blast radius (from `graphify affected`): 8 CLI commands, 3
server service functions, 1 evaluation evaluator, plus tests. Verified none
assume a single-file database — they only check `agentrouter.db` exists.

## Latest gates

| Check | Result |
|---|---|
| pytest | 844 passed, 3 skipped |
| branch coverage (gate 80%) | 85.65% |
| ruff check / format | clean, 319 files |
| bandit (`agentrouter` + `scripts`) | 0 issues |
| mutation gate (at `c11ddec`) | PASS — 0.9858 overall, safety 0.9877, engine 0.9815, 0 unreviewed survivors |

## Next action

```bash
cd "/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros"
findmnt -T "$PWD" -o OPTIONS          # confirm rw first
source "$HOME/.venvs/agentrouter/bin/activate"
export PATH="$HOME/.local/bin:$PATH"
```

Then: implement a **WAL-safe snapshot** in `agentrouter/store.py` (SQLite backup
API or an explicit checkpoint), prove a snapshot taken with a WAL active is
complete, and add the regression test.

Following actions:

1. Extend the reliability lab: failure injection (read-only data dir, corrupt
   catalog, oversized body, malformed Unicode, idempotency conflict, rate-limit
   burst, cancelled request), concurrency/state-integrity properties, and a soak
   profile that is **not** mandatory on ordinary PRs.
2. Push TASK-018B, open a **draft** PR to the RC, repair CI, merge, delete the
   branch, refresh the graph from the new RC.
3. Close the missing TASK-018A adversarial security review (finding 2 above).
4. TASK-018C: unified `agentrouter doctor`, secret-safe diagnostic bundle,
   correlation-ID tracing, redaction fix, tested runbooks.

## Prohibited

Pushing to `main`; pushing directly to the RC; merging RC → main; force-push;
tags; PyPI/npm publication; deployment; paid inference; lowering any release,
coverage or mutation threshold; weakening tests; fabricating human annotation.
