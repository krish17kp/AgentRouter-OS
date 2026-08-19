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
| Active branch | `task/TASK-018C-operations-observability` |
| Current commit | `6662791` (**local only — not pushed**) |
| Remote branch | none yet for TASK-018C |
| RC | `release/agentrouter-v0.5-rc1` @ **`ff06910`** (PR #10 merged) |
| `main` | `602321a`, untouched |
| Open PR | none. PR #9 and #10 both **merged**; branches deleted |
| Milestone | EPIC TASK-018 — production reliability & operational resilience |
| Phase | **TASK-018C** (operations + observability) starting |

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

0. ~~Owner decision on the breaking change~~ — **APPROVED** by the owner and
   merged in PR #10. The eight `constraint_tightened` acceptances stand in
   `contracts/http/v1/manifest.json`.

1. ~~WAL sidecar hazard~~ — **FIXED** in `fffb716`. `store.snapshot()` uses
   SQLite's online backup API. Measured before the fix: a plain copy of
   `agentrouter.db` after `init` + 5 writes reported **0 rows, silently**.
   TASK-018C's diagnostic bundle and any backup runbook must go through
   `store.snapshot`, never a filesystem copy.
2. ~~TASK-018A security re-review never returned~~ — **CLOSED**. An adversarial
   pass was executed against the merged surfaces; results in
   `loop/tasks/TASK-018B-reliability-load-lab/security-review-018a.md`.
   **No new critical or high findings.** All eight attacks (baseline tampering,
   `$ref` bombs, complexity DoS, `/ready` amplification, redaction, malicious
   ids, symlink/hardlink write targets, parity temp resources) behaved
   correctly. Caveat recorded there: I ran it myself, so it is reproducible but
   not independent — the delegated attempt is what failed.
3. ~~Redaction over-matches file paths~~ — **FIXED** in `2dfbf96`. The
   discriminator is a digit: path segments are words, opaque tokens are not, and
   every realistic slash-containing secret (AWS secret access key, base64 blob)
   carries a digit. Only the catch-all was narrowed; 16 credential formats are
   asserted still masked and four real paths preserved.

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
| pytest | 925 passed, 3 skipped |
| branch coverage (gate 80%) | 85.65% |
| ruff check / format | clean, 322 files |
| bandit (`agentrouter` + `scripts`) | 0 issues |
| mutation gate (at `c11ddec`) | PASS — 0.9858 overall, safety 0.9877, engine 0.9815, 0 unreviewed survivors |

## TASK-018B outcome (merged, PR #10 → `ff06910`)

Five real defects, each **reproduced before being fixed**, each pinned by a test
proven to fail without the fix:

1. Concurrent routing returned HTTP 500 (`database is locked`) — no WAL, no
   `busy_timeout`. Does **not** reproduce through `TestClient`; only against a
   real loopback server at 200 concurrent.
2. The WAL fix introduced a silent backup hazard — a plain copy of
   `agentrouter.db` reports **0 rows, no error**. Fixed with `store.snapshot()`.
3. An unbounded `task` was a disk-fill primitive (2 MB → 4 MB response + 4 MB
   row). Fixed with bounded request fields — the accepted breaking change.
4. Idempotent POSTs were not idempotent: 12 concurrent same-key requests →
   **6 decisions**. Fixed with per-key single-flight.
5. **CI caught what the dev machine could not**: WAL + 5s timeout was enough
   locally and not on slower runners. Writers are now serialised in-process —
   SQLite takes one writer anyway, so queueing beats racing. Verified at double
   CI's concurrency: 400 requests / 64 workers, zero errors.

Two CI repairs along the way, neither by weakening anything: 8 mutants killed
with real unit tests (`safety_policy_execution` 0.9772 → **0.9879**), and the
soak's Unix-only `resource` import made portable for the Windows matrix.

## Next action

```bash
cd "/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros"
findmnt -T "$PWD" -o OPTIONS          # confirm rw first
source "$HOME/.venvs/agentrouter/bin/activate"
export PATH="$HOME/.local/bin:$PATH"
```

**TASK-018C is partly built.** Done so far (all local, unpushed):

- `agentrouter/diagnostics.py` + `agentrouter doctor [--json]` — 11 checks with
  stable ids and remedies, aggregating the primitives the three existing doctors
  call rather than reimplementing them. A check never raises and never prints a
  secret; both are tested. Warnings do not fail (open local mode is the
  documented default), exit 0 healthy / 1 broken.
- Redaction narrowed so tracebacks keep their paths (finding 3, closed).
- `agentrouter/bundle.py` + `doctor --bundle [--include-database]` — allowlisted,
  never globbed; `.env` and credential files provably excluded; database via
  `store.snapshot`; refuses overwrite and symlinked destinations.

Remaining for TASK-018C:

1. **Correlation-ID tracing** end to end: API → service → store → logs → SDK
   response. Assert one id appears at every layer for a single request.
2. **Metrics cardinality** — ensure no label derives from request ids, prompts,
   users or arbitrary model text.
3. **Operational runbooks**, tested where they are local procedures, and
   explicitly labelled where they are hypothetical production ones. Cover at
   minimum: SQLite locked, database recovery, corrupted catalog + rollback,
   rate-limit overload, idempotency conflict, degraded host, diagnostic-bundle
   collection, and the **NTFS read-only remount** this project has actually hit.
4. Push, draft PR to RC, repair CI, merge, delete branch, refresh graph.
5. Then the post-milestone Graphify gap analysis to choose the next milestone.

## Prohibited

Pushing to `main`; pushing directly to the RC; merging RC → main; force-push;
tags; PyPI/npm publication; deployment; paid inference; lowering any release,
coverage or mutation threshold; weakening tests; fabricating human annotation.
