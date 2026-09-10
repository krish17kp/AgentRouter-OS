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
| Last updated | 2026-09-10 |
| Repository | `/mnt/NewVolume/Krish/04 - Dev Projects/Agentrouteros` |
| Filesystem | NTFS/fuseblk, verified **rw** this session |
| Active branch | `task/dynamic-skill-discovery`, stacked: RC `7068887` → `task/repo-cleanup-architecture-ponytail` `e678860` → `task/dynamic-skill-discovery` `fe4d13e` (both pushed, no PR yet) → this session's TASK-020 work |
| RC | **`7068887`** (merge of PR #12, TASK-018-state-reconcile). Pre-existing 018-era gates (`936 passed`, mutation PASS) are from `d81ad94`; this session's full pytest/ruff/bandit/pip-audit run (below) is against the current branch tip, not a fresh mutation run |
| `main` | `602321a`, untouched |
| Open PR | **#13** (`task/TASK-019-plugin-installer-hardening`, DRAFT, out of scope this session — do not touch). No PR yet for `task/repo-cleanup-architecture-ponytail` or `task/dynamic-skill-discovery`; both need one |
| Milestone | **Production Milestone 1 (TASK-020) COMPLETE** — pre-flight harness identity + usage/quota intelligence, see below |
| Next milestone | **TASK-019** — plugin installer hardening (PR #13 already drafted; independently selected, unchanged priority) |

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

## Production Milestone 1 (TASK-020) — what shipped

**Architecture publication**: the four canonical diagrams (already finalized
in `2de5cae` on `task/repo-cleanup-architecture-ponytail`, still `img1-4.png`
with no landing page) renamed to descriptive filenames
(`01-orchestration-routing-dispatch.png` … `04-workspace-layer-maintainer-interfaces.png`)
and given a `docs/architecture/README.md` landing page; root `README.md`'s
Architecture section now links there instead of embedding all four images
inline.

**Harness identity + usage/quota intelligence** (`loop/tasks/TASK-020-preflight-model-intelligence/`):
a discovery pass first established that most of "Milestone 1" already existed
— `engine.py` (complexity-weighted scoring + explanation trail),
`hosts.py`/TASK-016 (verified execution-host states), `refresh.py` (dynamic
catalog discovery), `diagnostics.py`/TASK-018C (the `doctor` Check pattern) —
so only two real gaps were built: `agentrouter/harness.py` (introspective,
evidence-only harness detection: Claude Code via a verified `CLAUDECODE` env
var, CI via `CI`/`GITHUB_ACTIONS`, GENERIC/UNKNOWN otherwise — no other tool
is guessed) and `agentrouter/usage.py` (a usage/quota state model —
UNKNOWN/UNSUPPORTED/AVAILABLE/EXHAUSTED/ERROR — honestly UNSUPPORTED for
every real provider today, since no live-credentialed adapter is registered;
`loop/BACKLOG.yaml` P2 already tracks that as owner-credential-gated). Wired
opt-in only: `doctor --verify-live` and `route --verify-live`; zero behavior
change without the flag.

Three independent read-only reviews (verification-engineer,
security-reviewer-arros, product-architect) found 0 CRITICAL/HIGH, 3 MEDIUM
security findings (unenforced timeout; unsanitized adapter-supplied text;
inconsistent provider-id namespace between `doctor` and `route`'s usage
lookups), 2 LOW, and 1 correctness bug (duplicated exclusion entries on a
quota-triggered re-rank) — all reproduced and fixed; see
`loop/tasks/TASK-020-preflight-model-intelligence/repairs.md`. Full
regression after repairs: **970 passed, 3 skipped** (baseline 936/3, so +34
new tests, 0 regressions); ruff/bandit/pip-audit clean.

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

## Latest gates

| Check | At | Result |
|---|---|---|
| pytest | `d81ad94` (018-era) | 936 passed, 3 skipped |
| branch coverage (gate 80%) | `d81ad94` | 85.42% |
| mutation gate | `d81ad94` | PASS — 0.986 overall, safety 0.9879, engine 0.9815 |
| contract check | `d81ad94` | unchanged; 8 owner-accepted |
| pytest | this session, `task/dynamic-skill-discovery` + TASK-020 | **970 passed, 3 skipped** |
| ruff check / format | this session | clean, 348 files |
| bandit (`agentrouter`) | this session | 0 issues |
| pip-audit | this session | no known vulnerabilities |

Coverage/mutation were **not** re-run this session (TASK-020's diff is small
and covered by targeted + full pytest; a fresh mutation run belongs to
whichever task next touches a mutation-gated module).

## Next action

First, close out this session's two un-PR'd branches and TASK-020's commits:

```bash
cd "/mnt/NewVolume/Krish/04 - Dev Projects/Agentrouteros"
findmnt -T "$PWD" -o OPTIONS          # confirm rw first
gh pr create --base release/agentrouter-v0.5-rc1 --head task/repo-cleanup-architecture-ponytail --draft
gh pr create --base task/repo-cleanup-architecture-ponytail --head task/dynamic-skill-discovery --draft
gh pr checks <the resulting PR numbers>   # inspect CI on both before marking ready
```

Then resume **TASK-019** — it is **already in progress**, not a fresh start:
PR **#13** (`task/TASK-019-plugin-installer-hardening`) is DRAFT with several
commits already landed (symlink/hardlink attacks, a raw-`OSError` fix, a
directory-removal recovery path with mutation-kill tests). Read
`loop/tasks/TASK-019-plugin-installer-hardening/` (if present) and PR #13's
current CI state before doing anything — do **not** `git checkout -b` a new
branch over it.

```bash
source "$HOME/.venvs/agentrouter/bin/activate"
export PATH="$HOME/.local/bin:$PATH"
git checkout task/TASK-019-plugin-installer-hardening && git pull --ff-only
gh pr view 13
```

**Plugin installer hardening — original rationale**, still valid. Chosen by
graph-driven gap analysis of the final RC, not by picking a convenient
cleanup. Three signals agreed:

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
