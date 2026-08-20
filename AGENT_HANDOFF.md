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
| Open PR | **#13 (draft)** → RC. PRs #9–#12 merged; branches deleted |
| Milestone | EPIC TASK-018 complete. **TASK-019 in progress** — head `fdc0cad` |
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

## TASK-019 — plugin installer hardening

`agentrouter/plugins.py` is the only module that writes into directories outside
the project (`~/.claude`, `~/.codex`) and then deletes from them.

**The backlog's premise was half wrong, and that is the headline.** It said the
module's safety claims had never been adversarially tested. They had not been —
but they were all *true*. Symlinked destination, symlinked parent, dangling link,
hardlinked destination, path traversal in a plugin name, uninstall after a user
edit, uninstall of an unmanaged file, uninstall with the ownership record
deleted, a directory populated during cleanup, a colliding backup, concurrent
install/uninstall, both upgrade paths: **every defence held.** What was missing
was proof, not protection — nothing in CI would have noticed a refactor that
removed one.

**Five real defects, each reproduced before it was fixed:**

1. a full disk during `plugin install` gave exit 1, **empty output** and a raw
   traceback — `_temp_file` let a bare `OSError` escape;
2. an unknown plugin name was echoed back **unbounded and unsanitised** (5 KB in,
   5 KB out, CR/LF intact). Same class as the API's `decision_id`, so the
   sanitiser moved to `observability.safe_echo` and both surfaces share it;
3. **that sanitiser was itself incomplete** — U+2028/U+2029 are not control
   characters but *are* line boundaries to `str.splitlines()`, so the forged-line
   attack still worked. Found by attacking my own fix; the test now derives the
   boundary set from Python rather than restating a range list;
4. `plugin list` and `plugin doctor` **crashed with a raw traceback** on a
   symlinked destination — the exact state they exist to explain. `--json` was
   correct throughout, which identified it as a display bug: `status()` let
   `_safe_dest`'s refusal escape. It now returns `blocked` and never raises;
5. **mine, and the one worth remembering** — a test I wrote for (4) omitted the
   `root` fixture, so `dest_root()` fell back to `Path.home()` and it created a
   symlink in the developer's **real** `~/.claude/skills/`. It passed in
   isolation, broke an unrelated test in another file, and aborted the mutation
   run by failing mutmut's baseline. The stray symlink and directory were
   removed and the user's 37 other skills verified untouched.
   `tests/conftest.py` now asserts after **every** test that the real plugin
   destinations are unchanged, cleans up a leak so it cannot cascade, and fails
   naming the missing fixture.

**Mutation gate** extended to the four functions that decide whether a path is
safe to write through and whether something is ours to delete (`_safe_relative`,
`_is_link_or_reparse`, `_entry_matches`, `_remove_owned_empty_directory`).
Wiring took three attempts and **the gate caught every mistake rather than
scoring it a pass**: no mutants generated → all `no_tests` → 73 genuine
survivors. Driven 73 → 0 by real tests. The 26 that remain are individually
proven equivalent, each with a written reason naming the clause that makes it
unobservable. No threshold lowered, nothing blanket-allowlisted.

**Honest boundaries kept.** The Windows `ctypes`/`CreateFileW` reparse-point
branch is unreachable on Linux, so the module's Linux coverage ceiling is about
91.4%; `tests/test_plugins_platform.py` states plainly that the POSIX suite
proves nothing about it, and skip-marks the Windows-only assertions.

## Latest gates (local, at `3bc01a5`, all green)

| Check | Result |
|---|---|
| pytest | **1116 passed, 6 skipped** |
| branch coverage (gate 80%) | **86.26%** |
| `plugins.py` coverage | 74% (Linux ceiling ~91.4%) |
| ruff check / format | clean, 338 files |
| bandit (`agentrouter` + `scripts`) | 0 issues |
| mutation gate | **PASS** — 0.9679 overall, safety 0.9633, engine 0.9815, **0 unreviewed survivors**, 4m36s |

**CI budget question is settled with real data, not an estimate:** the
`critical-modules` job ran in **3m45s** on a GitHub runner against its
45-minute timeout, so the enlarged campaign is not close to the limit.

## Graph

| Field | Value |
|---|---|
| Graphify | **0.9.47** at `~/.venvs/graphify`, linked into `~/.local/bin` |
| Rebuilt | 2026-08-20 from the TASK-019 tree |
| Size | **3830 nodes, 7514 edges, 301 communities** (was 3623/7084/309) |
| Verified | `safe_echo`, `_remove_owned_empty_directory`, `diagnose_all`, `_temp_file` blast radii checked line-by-line against source |

**Graph limitation, found and confirmed:** `graphify affected "safe_echo"` returns
**zero** hits in `agentrouter/server/app.py`, because those three call sites reach
it through the module-level alias `_echo = observability.safe_echo`. AST-only
extraction cannot follow a rebinding, so a blast-radius query on that symbol
silently omits the entire HTTP API surface. Verified against the source, which
wins. Treat `affected` output as a lead, never as a complete caller list.

## Open findings

None outstanding. All three findings tracked through this milestone are closed:
the WAL sidecar hazard (fixed via `store.snapshot`), the missing 018A security
re-review (executed, no new critical/high), and the redaction path over-match
(fixed without weakening detection).

## Prohibited

Pushing to `main`; pushing directly to the RC; merging RC → main; force-push;
tags; PyPI/npm publication; deployment; paid inference; lowering any release,
coverage or mutation threshold; weakening tests; fabricating human annotation.
