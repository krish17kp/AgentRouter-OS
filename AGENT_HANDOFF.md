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
| Last updated | 2026-08-19 (session 2) |
| Repository | `/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros` |
| Filesystem | NTFS/fuseblk, verified **rw** this session |
| Active branch | `task/TASK-018B-reliability-load-lab` |
| Current commit | `7ad153a` (pushed) |
| Remote branch | `origin/task/TASK-018B-reliability-load-lab` @ `7ad153a` |
| RC | `release/agentrouter-v0.5-rc1` @ `c11ddec`, post-merge CI **green** (CI, Security, Critical Mutation Testing) |
| `main` | `602321a`, untouched |
| Open PR | **#10 (draft)** → RC — `critical-modules` FAILED, fix staged locally |
| Milestone | EPIC TASK-018 — production reliability & operational resilience |
| Phase | TASK-018B (reliability/load lab) in progress |

## Release truth

**NOT RELEASE READY.** `context_band_accuracy = 0.6667` against the unchanged
`0.90` frozen-holdout gate. The other six gates pass. Only the two-real-human
annotation round in `TASK_012_OWNER_ACTIONS.md` can close it. No AI may act as
Annotator A, Annotator B or adjudicator; the frozen holdout must not be tuned
against; the threshold must not be lowered.

## Completed

- **Durable memory installed** — `CLAUDE.md` bootstrap + this canonical handoff
  (`fffb716`). `CODEX_HANDOFF.md` now defers to this file.
- **Graphify 0.9.47** installed and the graph built/verified (see Graph below).

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
- **TASK-018B, second defect** — WAL sidecar hazard, fixed via `store.snapshot`.
- **TASK-018B, third defect** — unbounded request fields (see finding 0).
- **Failure-injection suite** — `tests/test_failure_injection.py`, 21 tests, one
  shared survivability contract per injected failure.
- **TASK-018B, fourth defect** — idempotent POSTs were not idempotent: 12
  concurrent requests with the same key + body produced **6 distinct decisions**
  (`get`/`put` each locked, the window between them was not). Fixed with per-key
  single-flight in `7ad153a`.

## In progress / open findings

0. **OWNER DECISION PENDING — a deliberate breaking API change is staged.**
   `8221cf4` bounds previously-unbounded request fields and records eight
   `constraint_tightened` acceptances in `contracts/http/v1/manifest.json`.
   Justification is measured, not theoretical: a 2 MB `task` returned 200 OK,
   produced a 4,004,603-byte response and a 4,005,888-byte database row, from one
   caller, unbounded — the API is local and open by default. Bounds are generous
   (100k chars ≈ 25k tokens). **Do not merge the TASK-018B PR without flagging
   this acceptance for owner sign-off**; it is visible in the manifest diff.
   Flagged at the top of PR #10's description. PR is **draft and unmerged**.

1. ~~WAL sidecar hazard~~ — **FIXED** in `fffb716`. `store.snapshot()` uses
   SQLite's online backup API. Measured before the fix: a plain copy of
   `agentrouter.db` after `init` + 5 writes reported **0 rows, silently**.
   TASK-018C's diagnostic bundle and any backup runbook must go through
   `store.snapshot`, never a filesystem copy.
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
| pytest | 873 passed, 3 skipped |
| branch coverage (gate 80%) | 85.65% |
| ruff check / format | clean, 322 files |
| bandit (`agentrouter` + `scripts`) | 0 issues |
| mutation gate (at `c11ddec`) | PASS — 0.9858 overall, safety 0.9877, engine 0.9815, 0 unreviewed survivors |

## CI state on PR #10 (at `7ad153a`)

All green except **`critical-modules` (mutation gate): FAIL**. Not a threshold
miss — scores still pass (`safety_policy_execution` 0.9772 ≥ 0.95, overall
0.9785). The failing gate is `all_survivors_reviewed_non_bypass`: **8 unreviewed
survivors**, every one in the new `IdempotencyCache.flight` / `.release_flight`
added by `7ad153a`.

Repaired locally (uncommitted at time of writing) with six real unit tests in
`tests/test_server_limits.py` that pin the semantics the mutants attack: same
lock for the same key, different locks for different keys, an idle lock is
dropped, a **held** lock is not dropped, an unknown key is a no-op, and the locks
genuinely serialise the same key with no interleaving. **No threshold lowered and
nothing allowlisted** — allowlisting would have been wrong here, since these are
live mutants in new logic, not equivalent ones.

Local mutation re-run in progress to confirm before pushing.

## Next action

```bash
cd "/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros"
findmnt -T "$PWD" -o OPTIONS          # confirm rw first
source "$HOME/.venvs/agentrouter/bin/activate"
export PATH="$HOME/.local/bin:$PATH"
```

Then: watch CI on **PR #10** and repair genuine failures. Remaining TASK-018B
surface still to build: a **soak profile** (explicitly not mandatory on ordinary
PRs), concurrent host detection, catalog read during atomic replacement, and a
deterministic CI reliability job wired into `.github/workflows/ci.yml`.

Following actions:

1. Close the missing TASK-018A adversarial security review (finding 2).
2. Push TASK-018B, open a **draft** PR to the RC, repair CI, merge, delete the
   branch, refresh the graph from the new RC.
3. Close the missing TASK-018A adversarial security review (finding 2 above).
4. TASK-018C: unified `agentrouter doctor`, secret-safe diagnostic bundle,
   correlation-ID tracing, redaction fix, tested runbooks.

## Prohibited

Pushing to `main`; pushing directly to the RC; merging RC → main; force-push;
tags; PyPI/npm publication; deployment; paid inference; lowering any release,
coverage or mutation threshold; weakening tests; fabricating human annotation.
