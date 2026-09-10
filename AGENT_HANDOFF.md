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
| Active branch | `release/agentrouter-v0.5-rc1` (checked out locally at RC tip) |
| RC | **`62d5289`** (merge of PR #15, dynamic-skill-discovery + TASK-020, into PR #14's cleanup, both merged into RC this session). `task/repo-cleanup-architecture-ponytail` and `task/dynamic-skill-discovery` are fully merged, deleted locally, and safe to delete on the remote (blocked from doing so here by the repo's own `pre_tool_guard` hook, which categorically refuses remote-branch deletion) |
| `main` | `602321a`, untouched — RC is 66 commits ahead, PR **#16** open (`release/agentrouter-v0.5-rc1` → `main`) |
| Open PRs | **#16** (RC → `main`, promotion PR, open — see Release truth below) · **#13** (`task/TASK-019-plugin-installer-hardening`, DRAFT, out of scope, do not touch — now 11 commits behind RC; real future conflicts confirmed via `git merge-tree` in `AGENT_HANDOFF.md`, `agentrouter/diagnostics.py`, `tests/conftest.py` (add/add)) |
| Milestone | **Branch consolidation + RC→main promotion attempt COMPLETE this session** — PR #14 and #15 merged into RC, full RC validation green, PR #16 opened and its `enforce-release-gate` genuinely run (not skipped); blocked only by the known human-annotation gate, see below |
| Next milestone | **TASK-019** — plugin installer hardening (PR #13, DRAFT, in progress; resume from its own state, do not restart) |

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

## Branch consolidation + RC→main promotion attempt (this session)

PR #14 (repo cleanup + architecture) merged into RC as `1ae3155`; PR #15
(dynamic skill discovery + TASK-020) retargeted from the now-merged cleanup
branch straight to RC and merged as `62d5289` — recalculated diff verified
identical to the pre-retarget diff (tree of `1ae3155` is byte-identical to
`e678860`, so no code moved under the retarget). Full RC validation on
`62d5289`: pytest 973 passed/3 skipped, ruff+format clean, bandit 0, pip-audit
(against `requirements.txt`) clean, wheel/sdist build + clean-venv install/CLI
smoke pass (harness correctly detects `claude-code` outside the repo), SDK
typecheck+tests pass (14/18, 4 skipped), and CI (full matrix + api-compatibility
+ build-smoke + critical-modules + security scan) green on the merged head.
Two independent read-only reviews of the combined `7068887..62d5289` diff
(product-architect, security-reviewer-arros) found 0 regressions and 0
CRITICAL/HIGH; architecture review's one actionable finding (a stale
"gitignored" claim in `.claude/SKILL_POLICY.md`) is fixed; the rest are
pre-existing/out-of-scope LOW items, not attributable to this integration.

PR **#16** (`release/agentrouter-v0.5-rc1` → `main`) opened to exercise the
real `enforce-release-gate` (it only runs for a PR whose base is `main`, a
release tag, or explicit dispatch — never skipped here). It ran and **failed
on exactly one of seven gates**: `context_band_accuracy>=0.90` — measured
`0.6667` (n=45 held-out cases), unchanged from every prior session. All six
other gates pass (`task_type_macro_f1`, `high_risk_recall`,
`approval_accuracy`, `tool_needs_f1`, `high_risk_gated`,
`synthetic_routing_top1`). This is the known, legitimate, non-bypassable
human-annotation gate — not a software defect. **PR #16 is intentionally
left open, not merged.** Closing it requires the real two-annotator round in
`TASK_012_OWNER_ACTIONS.md`; no AI may act as annotator or adjudicator, the
frozen holdout must not be tuned against, and the threshold must not be
lowered.

Both merged task branches (`task/repo-cleanup-architecture-ponytail`,
`task/dynamic-skill-discovery`) are fully reachable from RC
(`git merge-base --is-ancestor` verified) and were deleted locally. The
remote copies were **not** deleted — the repo's `pre_tool_guard` hook
categorically refuses `git push --delete` on any remote branch, and that
refusal was respected rather than routed around; the owner can delete
`origin/task/repo-cleanup-architecture-ponytail` and
`origin/task/dynamic-skill-discovery` directly on GitHub.

TASK-019 (PR #13, still DRAFT, untouched) is now 11 commits behind RC. A
read-only `git merge-tree` dry run (no branch or working-tree state changed)
confirms **real future conflicts**, not just GitHub's shallow "mergeable"
signal: `AGENT_HANDOFF.md` (trivial, doc churn), `agentrouter/diagnostics.py`
(real — TASK-018C's doctor pattern and TASK-019's own "plugin doctor" check
both touch it), and `tests/conftest.py` (add/add — both branches
independently consolidated the same fixtures). Whoever resumes TASK-019
should rebase onto current RC early, expect a real (not mechanical) merge in
`diagnostics.py`, and re-run mutation coverage on that file after resolving
it.

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
| pytest | this session, merged RC `62d5289` | **973 passed, 3 skipped** |
| ruff check / format | this session, RC `62d5289` | clean |
| bandit (`agentrouter`) | this session, RC `62d5289` | 0 issues |
| pip-audit (`requirements.txt`) | this session, RC `62d5289` | no known vulnerabilities |
| build + clean-venv install/CLI smoke | this session, RC `62d5289` | pass |
| sdk/typescript typecheck + test | this session, RC `62d5289` | pass (14 pass, 4 skipped) |
| CI (full matrix, api-compat, build-smoke, critical-modules, security) | this session, RC `62d5289` | all green |
| `enforce-release-gate` (real, PR #16 base=`main`) | this session | **FAIL** — only `context_band_accuracy` (0.6667 < 0.90); other 6 gates pass |

Critical-module mutation gate was confirmed via CI's `Critical Mutation
Testing` workflow (pass) on RC `62d5289`, not re-run locally this session.

## Next action

Resume **TASK-019** — it is **already in progress**, not a fresh start:
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

None blocking. All three EPIC-018 findings are closed: the WAL sidecar hazard
(fixed via `store.snapshot`), the missing 018A security re-review (executed,
no new critical/high), and the redaction path over-match (fixed without
weakening detection). This session's consolidation reviews surfaced only LOW
severity, pre-existing/out-of-scope items (see the consolidation section
above) — none rise to a fix-now bar under this repo's "don't reopen a
finished milestone for stylistic reasons" policy. The one real open item is
the TASK-019/RC conflict risk in `agentrouter/diagnostics.py` and
`tests/conftest.py`, noted above for whoever resumes TASK-019.

## Prohibited

Pushing to `main`; pushing directly to the RC; merging RC → main; force-push;
tags; PyPI/npm publication; deployment; paid inference; lowering any release,
coverage or mutation threshold; weakening tests; fabricating human annotation.
