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
| RC | **`64ae5f8`** (merge of PR #18, TASK-012 pack-blinding fix, on top of PR #17's docs, on top of PR #14+#15). Four task branches are fully merged and safe to delete on the remote (blocked from doing so here by the repo's own `pre_tool_guard` hook, whose documented policy refuses remote-branch deletion as a category, not just the specific `git push --delete` pattern it checks — not routed around via `gh api` either): `task/repo-cleanup-architecture-ponytail`, `task/dynamic-skill-discovery`, `task/consolidation-handoff-docs`, `task/TASK-012-pack-blinding-fix` |
| `main` | `602321a`, untouched — RC is 70 commits ahead, PR **#16** open (`release/agentrouter-v0.5-rc1` → `main`) |
| Open PRs | **#16** (RC → `main`, promotion PR, open — see Release truth below) · **#13** (`task/TASK-019-plugin-installer-hardening`, **NOW READY FOR REVIEW** — merged forward onto current RC, independent security review closed, mutation gate PASS 0.9688/0 unreviewed survivors, full CI green; still not merged, per instruction) |
| Milestone | **Release-gate preparation (Track A) + TASK-019 resume (Track B) COMPLETE this session** — see below |
| Next milestone | Merge PR #13 (owner decision, out of this session's authorization) once reviewed; then whatever gap analysis selects next. The two-annotator round (`TASK_012_OWNER_ACTIONS.md`) is the only path to closing PR #16 |

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

## Release-gate preparation + TASK-019 resume (this session)

**Track A — human annotation tooling, verified not fabricated.** All seven
`TASK_012_OWNER_ACTIONS.md` CLI commands confirmed to exist with matching
flags; the 63-candidate pool intact; the frozen-holdout leakage guardrail
confirmed as real enforced code in `agentrouter/annotation/splits.py`; 35
annotation tests passing; nothing in `agentrouter/annotation/*` touched by
the branch consolidation. One real, pre-existing defect found by a read-only
verification pass (not attributable to this session's other work): `dataset
pack` did not honor its own blinding promise — `Candidate.template` (which
literally encodes the intended band, e.g. `"review/small"`) and `notes`
survived into the pack YAML an annotator opens. Fixed on its own branch
(PR #18, merged) at the shared choke point (`build_pack()`), verified via
the real CLI that a freshly generated pack now has zero `template:`/`notes:`
occurrences. **The pipeline is genuinely ready to hand to two real human
annotators now** — see the Next human action section this session's final
report gave (not persisted here; re-derive from `TASK_012_OWNER_ACTIONS.md`
plus `agentrouter dataset pack --annotator A/B --seed <distinct> --out
<path>` if this file is the only thing surviving).

**Track B — TASK-019 resumed, not restarted.** Merged current RC into
`task/TASK-019-plugin-installer-hardening` (two merges, since RC advanced
again mid-session with PR #18): the `diagnostics.py`/`conftest.py`/
`AGENT_HANDOFF.md` conflicts predicted above were resolved exactly as
predicted — `run_all()`'s two independently-added `Check` entries both kept,
`conftest.py`'s two non-overlapping fixtures (RC's `home`, TASK-019's
`_never_touch_the_real_home`) combined rather than one superseding the
other, `AGENT_HANDOFF.md` took RC's version outright. Verified the PR body's
own "still to come" list (mutation coverage, security review, Graphify
re-check, documentation) was **already stale** before this session touched
anything — `task.yaml`'s `results` section and real CI history on the branch
tip already showed mutation PASS at 0.9679; only the security review and
Graphify re-check were genuinely outstanding.

An independent `security-reviewer-arros` pass over the complete TASK-019
diff found 0 CRITICAL/HIGH, 3 MEDIUM, 2 LOW — all fixed, all reproduced
before and after:
`plugin list`/`doctor`/`uninstall` traceback on a hostile `0o000`
directory (`_is_link_or_reparse`'s `path.is_symlink()` and `_path_exists`
both caught only `FileNotFoundError`, not `PermissionError`); `safe_echo`'s
hand-curated bidi/zero-width range list missed real codepoints (replaced
with a Unicode-category `Cc`+`Cf` check, comprehensive and future-proof);
`tests/conftest.py`'s autouse safety net used to *delete* a leaked write
into the developer's real home before failing (itself a data-loss
primitive — now fails loudly, leaves the path alone); a loose fault-injection
test assertion, tightened, exposed a real gap in `install()`'s
pre-validation loop (no `try/except` at all, unlike the loop right after it
— fixed at the shared `_src_bytes` choke point and the call site).

Fixing `_is_link_or_reparse` renumbered every mutant inside it, turning 7
into unreviewed CI survivors. Each was hand-verified (mutmut's CLI was too
slow locally for a full campaign; mutant diffs pulled individually via
`mutmut show`, then applied by hand to confirm each new test actually fails
against them before being reverted): 3 were real gaps, now killed with
tests in `tests/test_plugins_decisions.py`; 4 were genuinely equivalent,
re-verified fresh (not carried forward) and re-allowlisted under their new
numbers. Final mutation gate: **PASS at 0.9688 overall, 0 unreviewed
survivors**, confirmed by CI's `critical-modules` job, not just locally.

PR #13's stale description (the "still to come" list, the pre-merge commit
count) corrected to reflect actual verified state. Marked **ready for
review** (un-drafted) — all of `task.yaml`'s own acceptance criteria are
now genuinely met and CI is green — but **not merged**, per instruction.

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

**TASK-019 (PR #13) is DONE and ready for review — an owner decision to
merge, not further engineering.** Everything in `task.yaml`'s acceptance
criteria is met (every invariant tested, mutation gate PASS 0.9688/0
unreviewed survivors, every documented command executed by
`test_documented_commands.py`, no threshold lowered/test weakened/mutant
blanket-allowlisted) and CI is green on the current head. Do not reopen it
for stylistic reasons. If the owner merges it, refresh Graphify and pick the
next module by the same graph-driven gap analysis TASK-019 itself used
(size+coverage, hub centrality, blast-radius outside the project).

**The human-annotation round (`TASK_012_OWNER_ACTIONS.md`) is the only path
to closing PR #16.** The tooling is now genuinely ready — see Track A above.
If a fresh session is asked to help, it may prepare packs, verify file
integrity/schema, check commands, and run the pipeline after real labels
exist; it may **never** generate a label, adjudicate a disagreement, or tune
against the frozen holdout.

```bash
source "$HOME/.venvs/agentrouter/bin/activate"
export PATH="$HOME/.local/bin:$PATH"
gh pr view 13   # confirm still ready/green before assuming this file is current
gh pr view 16   # confirm still blocked only by context_band_accuracy
```

## Open findings

None blocking. All three EPIC-018 findings are closed: the WAL sidecar hazard
(fixed via `store.snapshot`), the missing 018A security re-review (executed,
no new critical/high), and the redaction path over-match (fixed without
weakening detection). TASK-019's independent security review findings (3
MEDIUM, 2 LOW) are all fixed and re-verified this session, see above. The
consolidation session's LOW-severity items remain pre-existing/out-of-scope,
below the fix-now bar under this repo's "don't reopen a finished milestone
for stylistic reasons" policy.

## Prohibited

Pushing to `main`; pushing directly to the RC; merging RC → main; force-push;
tags; PyPI/npm publication; deployment; paid inference; lowering any release,
coverage or mutation threshold; weakening tests; fabricating human annotation.
