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
| Last updated | 2026-08-20 (TASK-019 in progress) |
| Repository | `/media/krish/New Volume/Krish/04 - Dev Projects/Agentrouteros` |
| Filesystem | NTFS/fuseblk, verified **rw** this session |
| Active branch | `task/TASK-019-plugin-installer-hardening` |
| RC | **`7068887`**, CI + Security green (mutation gate green at `d81ad94`, docs-only since) |
| `main` | `602321a`, untouched |
| Open PR | none yet for TASK-019. PRs #9–#12 merged; branches deleted |
| Milestone | EPIC TASK-018 complete. **TASK-019 in progress** — commit `6a5055c` (local only) |
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

## TASK-019 progress — a correction worth recording

The backlog framed `plugins.py` as claiming safety properties that had "never
been adversarially tested". **Half of that was wrong.** The module is genuinely
well built: I attacked every claim it makes — symlinked destination, symlinked
parent, dangling link, hardlinked destination, path traversal, uninstall after a
user edit, uninstall of an unmanaged file, uninstall with the ownership record
deleted, populated directory during cleanup, colliding backup, concurrent
installs, concurrent install+uninstall, and both package-upgrade paths — and
**every one held**.

What was true is that none of it was *proven*. The defences worked, but nothing
in CI would have noticed a refactor removing one. Landed in `6a5055c`:

- `tests/test_plugins_adversarial.py` — 20 tests, each naming the damage it
  prevents. Verified to have teeth: neutering `_is_link_or_reparse` fails three,
  one by showing content written outside the plugin root.
- `tests/test_plugins_faults.py` — 12 fault-injection tests covering the error
  branches that make up most of the uncovered code.
- `tests/test_plugins_platform.py` — the honest boundary (see below).

**One real defect, found and fixed.** Every failure in the module raises a typed
`PluginError` with a remedy — except a write failure, which escaped as a bare
`OSError`. Reproduced through the CLI: a full disk gave **exit 1, empty output
and a raw traceback**. `_temp_file` now converts it, with a CLI-level regression
test.

**Coverage: 67.7% → 69.4%.** Deliberately not chased further yet — ~70 of the
818 statements are the Windows `ctypes`/`CreateFileW` branch of
`_remove_directory_by_handle`, unreachable on Linux, so the Linux ceiling is
about **91.4%**. `test_plugins_platform.py` states plainly that the POSIX suite
says nothing about the Windows reparse-point path, and skip-marks the
Windows-only assertions so they only pass where a Windows runner runs them.

## Remaining for TASK-019

1. Strengthen `plugin doctor` — diagnose installed / unmanaged / owned /
   modified / legacy / interrupted / recoverable / corrupt-ownership / missing
   destination / host-root-unavailable, with safe remedies, and surface it in
   unified `agentrouter doctor` without duplicating plugin logic.
2. Close more of the portable error branches (target the 91.4% ceiling
   honestly, not the 80% gate by accident).
3. Consider adding plugin destructive paths to the mutation-tested set.
4. Adversarial security review of the complete diff; refresh Graphify and
   re-run impact analysis on changed plugin symbols.
5. Docs: USER_GUIDE / SECURITY / KNOWN_LIMITATIONS / CHANGELOG / runbooks —
   documenting exactly what is guaranteed and what stays platform-dependent.
6. Draft PR to the RC, repair CI, merge, delete branch, refresh graph, reconcile
   state, then the next graph-driven gap analysis.

## Open findings

None outstanding. All three findings tracked through this milestone are closed:
the WAL sidecar hazard (fixed via `store.snapshot`), the missing 018A security
re-review (executed, no new critical/high), and the redaction path over-match
(fixed without weakening detection).

## Prohibited

Pushing to `main`; pushing directly to the RC; merging RC → main; force-push;
tags; PyPI/npm publication; deployment; paid inference; lowering any release,
coverage or mutation threshold; weakening tests; fabricating human annotation.
