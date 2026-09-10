# LOOP_LOG

## Iteration 30 — 2026-09-10 — Branch consolidation + RC→main promotion attempt

**Goal:** stop accumulating stacked feature branches; merge PR #14 (repo
cleanup + architecture) and PR #15 (dynamic-skill-discovery + TASK-020) into
the RC in dependency order, validate the integrated RC, and attempt the real
RC→main promotion — letting the real `enforce-release-gate` decide, not
assuming it would fail.

**What happened.** Inventoried actual GitHub state first rather than trusting
the prior handoff (it matched exactly: PR #14 → RC, PR #15 → cleanup branch,
PR #13/TASK-019 → RC draft, both #14/#15 CLEAN/MERGEABLE, CI green). Merged
PR #14 into RC (`1ae3155`); confirmed via `git diff --quiet` that the merge
commit's tree is byte-identical to the cleanup branch tip (no surprise
changes landed alongside it). Retargeted PR #15 from the cleanup branch to RC
via `gh api` (`gh pr edit`/`gh pr merge` both hit an unrelated `gh` CLI
GraphQL bug on this repo — `Projects (classic)` deprecation on the
`projectCards` field — routed around by calling the REST API directly);
recalculated diff verified unchanged (same file list, no duplicated cleanup
content, no TASK-019 files). Merged PR #15 into RC (`62d5289`).

**Full RC validation on `62d5289`.** pytest 973 passed/3 skipped; ruff
check+format clean; bandit 0 issues; pip-audit (`requirements.txt`) clean;
wheel+sdist build; clean-venv install outside the repo with CLI smoke
(`init`/`doctor`/`--help`) — harness correctly self-identified as
`claude-code`; `sdk/typescript` typecheck + 14/18 tests (4 skipped, all
pre-existing live-suite skips) pass; CI on the merged head (full Python
matrix, Windows, api-compatibility, build-smoke, critical-modules mutation
gate, security scan) all green. Two independent read-only reviews of the
combined `7068887..62d5289` diff (product-architect, security-reviewer-arros)
found 0 regressions and 0 CRITICAL/HIGH; the one actionable finding (a stale
"gitignored" claim about removed AutoSkills symlinks in
`.claude/SKILL_POLICY.md`) was fixed; the rest were LOW-severity and
pre-existing/out of scope (an unsanitized provider-id echo in
`usage.py:96`, a `shutdown(wait=False)` interpreter-exit nuance, and a
`pip-audit` discrepancy traced to dev-venv extras/contamination, not the
diff).

**RC→main, honestly.** Opened PR #16 specifically to exercise the real
`enforce-release-gate` (it only runs for a PR based on `main`, a release tag,
or explicit dispatch — confirmed by reading `.github/workflows/ci.yml`'s
`if:` condition before relying on it). It ran — not skipped — and failed on
exactly one of seven gates: `context_band_accuracy` measured `0.6667` (n=45
held-out) against the required `>=0.90`; every other gate
(`task_type_macro_f1`, `high_risk_recall`, `approval_accuracy`,
`tool_needs_f1`, `high_risk_gated`, `synthetic_routing_top1`) passed. This
matches every prior session's honest finding exactly — no regression, no
drift. **PR #16 was left open, not merged**, per the standing policy: this
gate needs the real two-human annotation round in
`TASK_012_OWNER_ACTIONS.md`, and no AI may act as annotator, adjudicator, or
tune the frozen holdout.

**Branch cleanup.** Both merged branches' commits proven fully reachable from
RC via `git merge-base --is-ancestor`; deleted locally. Remote deletion was
attempted and refused by the repo's own `pre_tool_guard` hook (categorical
block on `git push --delete` against any remote branch) — that refusal was
respected, not routed around; the two stale remote branches are left for the
owner to delete directly on GitHub.

**TASK-019, left alone but checked.** Confirmed read-only (via
`git merge-tree --write-tree`, which writes only a tree object, never
touches a branch ref or working tree) that TASK-019's branch — now 11
commits behind the new RC — has **real** future conflicts, not just GitHub's
shallow "mergeable" signal: `agentrouter/diagnostics.py` (both TASK-018C's
doctor pattern and TASK-019's own plugin-doctor check touch it) and
`tests/conftest.py` (add/add — both branches independently consolidated the
same fixtures). Recorded for whoever resumes TASK-019 next; the branch,
PR #13, and its commits were not touched.

**Verification:** all of the above reproduced with actual command output,
not inferred from prior CI runs; the `enforce-release-gate` conclusion is
from the real artifact JSON downloaded off the PR #16 run, not the
non-enforcing `release-readiness-report`.

## Iteration 29 — 2026-09-10 — Production Milestone 1 (TASK-020): harness identity + usage/quota intelligence

**Goal:** reconcile the two branches stacked above the RC since Iteration 28
(repo-cleanup/architecture, dynamic-skill-discovery), publish the four
canonical architecture diagrams properly, and implement the first production
architecture milestone — pre-flight, environment/harness discovery, and
model/usage intelligence.

**What discovery found first.** A `repo-explorer` pass before writing any code
established that most of "Milestone 1" already existed: `engine.py`'s
complexity-weighted scoring + explanation trail, `hosts.py`/TASK-016's
verified execution-host states, `refresh.py`'s dynamic catalog discovery, and
`diagnostics.py`/TASK-018C's `doctor` Check pattern. Building any of those
again would have duplicated real, tested abstractions. Only two real gaps
existed: introspective harness detection (what tool is running *this*
process, not what AgentRouter can dispatch to) and a usage/quota state model
distinct from host readiness.

**What shipped.** `agentrouter/harness.py` (evidence-only: Claude Code via a
verified `CLAUDECODE` env var present in this very session, CI via
`CI`/`GITHUB_ACTIONS`, GENERIC/UNKNOWN otherwise — Codex/Cursor/Antigravity
have zero runtime footprint in this repo per `integrations/README.md`, so
none was fabricated). `agentrouter/usage.py` (UNKNOWN/UNSUPPORTED/AVAILABLE/
EXHAUSTED/ERROR; honestly UNSUPPORTED for every real provider today since no
live-credentialed adapter is registered — `loop/BACKLOG.yaml` P2 already
tracks that as owner-credential-gated, not a code gap). Both wired opt-in
only: `doctor --verify-live`, `route --verify-live`; zero behavior change
without the flag. Also: the four architecture PNGs renamed to descriptive
filenames and given a `docs/architecture/README.md` landing page.

**What three independent read-only reviews found.** 0 CRITICAL/HIGH. 3 MEDIUM
from security-reviewer-arros: `check_usage`'s `timeout` parameter was accepted
but never enforced (fixed with `ThreadPoolExecutor` + `wait()` — deliberately
not `future.result(timeout=...)`, because `concurrent.futures.TimeoutError`
became an alias of the builtin `TimeoutError` on Python ≥3.11, which would
have misreported an adapter's own raised `TimeoutError` as our wall-clock
timeout, caught by this fix's own first test run on this machine's Python
3.12); an adapter-supplied `detail` string reached stdout/JSON/the SQLite
decision log unsanitized (fixed, mirroring `hosts._sanitize`); `doctor`
looked up a live-check registry by API host id while `route` looked up by
`ModelEntry.provider` id — two different namespaces for what a user would
assume is the same provider (fixed via a new `hosts.provider_for_api_host()`
mapping). 1 correctness bug from product-architect: a quota-triggered re-rank
duplicated every eligibility-exclusion entry (fixed — the recomputed retry's
exclusions are a pure-function duplicate of the original's, so only the new
quota-specific entry needed adding). 2 LOW/judgment-call items accepted as-is
with recorded rationale (see `loop/tasks/TASK-020-preflight-model-intelligence/repairs.md`).

**Verification.** Full regression after repairs: 970 passed, 3 skipped
(baseline 936/3 — +34 new tests, 0 regressions). ruff/bandit/pip-audit clean.
Real-environment smoke against a fresh `agentrouter init` home: `doctor`
1.13s, `doctor --verify-live` 0.98s, both truthful and secret-free; an
independent reviewer confirmed via `strace` that `doctor --verify-live` makes
zero `connect()` calls when nothing is registered.

**State at handoff.** `task/dynamic-skill-discovery` has this session's
commits but has not yet been pushed/PR'd (see AGENT_HANDOFF.md). Neither it
nor `task/repo-cleanup-architecture-ponytail` has a PR. PR #13 (TASK-019) is
untouched, still DRAFT, still the next milestone.

## Iteration 28 — 2026-08-20 — EPIC TASK-018 complete; graph-first loop established

**Goal:** finish the production reliability and operational resilience milestone —
TASK-018B and TASK-018C — and put a navigation layer and durable memory under the loop
so a fresh session can continue without conversation state.

**What the reliability lab actually found.** Five defects, none of them hypothesised in
advance; each was reproduced first, then fixed, then pinned by a test proven to fail
without the fix.

200 concurrent `POST /v1/route` against a real uvicorn server returned **3 × HTTP 500**,
`sqlite3.OperationalError: database is locked`. SQLite's default busy timeout is **zero**,
so the first contended write fails outright rather than waiting. The detail that mattered
methodologically: **this does not reproduce through `TestClient`** at 40 concurrent
requests. A harness built on TestClient would have declared the API healthy, which is why
the lab drives real loopback sockets.

Fixing it created a quieter problem. With a WAL active, `cp agentrouter.db` is **not a
backup** and fails silently — after `init` plus five writes a plain copy reports **0 rows**,
no error. That one was found by asking the graph what else touched the change:
`graphify affected "connect"` showed 8 CLI commands, 3 service functions and an evaluator,
which prompted "what else assumes this is one file?".

Failure injection then found an unbounded `task` field. It is echoed **and** persisted, so
2 MB in produced a 4,004,603-byte response and a 4,005,888-byte row — from one caller, on a
service open by default, with no ceiling. Bounding it is a breaking change; the checker
caught all eight tightenings and refused, which is the **first real use of the acceptance
workflow built in 018A**. It works end to end, including the base-branch check that would
otherwise block an accepted change forever. The owner was asked rather than self-approved.

And idempotent POSTs were not idempotent: **12 concurrent requests with the same key and
body produced 6 distinct decisions**, because `get` and `put` were each locked but the
window between them was not.

**CI caught what this machine could not.** WAL plus a 5 s timeout was enough here and not
enough on slower 3.10/3.11/Windows runners. Raising the timeout would have treated the
symptom; the shape was wrong. SQLite takes one writer at a time, so N threads racing for
the file lock is wrong by construction — they now queue in-process. Verified at double CI's
concurrency: 400 requests across 64 workers, zero errors.

Two CI repairs, neither by weakening anything. The mutation gate failed with 8 unreviewed
survivors, all inside the new single-flight lock. Allowlisting would have been wrong —
these were live mutants in new concurrency logic attacking exactly the properties the fix
depends on. Six real unit tests instead; `safety_policy_execution` 0.9772 → **0.9879**.
Then `test-windows` failed on a Unix-only `resource` import, which this project's
Windows-first stance makes a genuine portability bug rather than a CI quirk.

**018C: operations.** Three doctors already existed, each printing and exiting, so nothing
could answer "is this install healthy?" as data. `agentrouter doctor` aggregates the
primitives they call rather than reimplementing them, with stable check ids and a remedy on
every finding. Two rules with no exceptions: a check never raises (a diagnostic that
crashes is useless precisely when it is needed) and never prints a secret. Warnings
deliberately do **not** fail — open local mode with no API key is the documented default, so
exiting non-zero on a fresh healthy install would cry wolf on the happy path.

The diagnostic bundle is built from an **allowlist**, never a directory glob, because a glob
picks up whatever is sitting there — a `.env`, a credentials file. Ten tests each attack one
way something private could get in.

The redaction over-match from 018B is fixed without weakening detection. The discriminator
is a digit: path segments are words, opaque tokens are not, and every realistic
slash-containing secret carries one. Sixteen credential formats still masked, four real
paths preserved.

Twelve runbooks, each labelled **Verified** (with the backing test named), **Local
procedure**, or **Hypothetical**. Production incident response is Hypothetical and says so —
this project has no hosted deployment, and inventing backup rotation would be fabricating
operational experience it does not have.

**The security gap was closed, not dropped.** The 018A re-review that never returned was
executed: baseline tampering, `$ref` bombs, complexity DoS, `/ready` amplification,
redaction, malicious identifiers, symlink and hardlink write targets, parity temp resources.
No new critical or high findings. The honest caveat is recorded — I ran it myself, so it is
reproducible but not independent.

**Graph-first loop established.** Graphify 0.9.47 into a dedicated user venv (uv and pipx
absent, `pip --user` PEP 668-blocked), AST-only extraction so no LLM and no paid inference:
3623 nodes / 7084 edges from the final RC. Verified rather than trusted, and it earned its
keep on the silent-backup defect. `CLAUDE.md` + `AGENT_HANDOFF.md` now carry the state a
fresh session needs.

**Next milestone chosen by evidence, not convenience.** TASK-019, plugin installer
hardening: `plugins.py` is 818 statements at **67.7%** coverage (the next largest gap is
129 statements), owns four of the graph's top-14 hubs, and is the only module that writes
into directories outside the project and then removes files from them — while claiming in
its docstring exactly the class of safety property that 018A/B/C repeatedly found true in
intent and incomplete in practice.

**Final gates at `d81ad94`:** 936 passed / 3 skipped; branch coverage 85.42%; ruff clean
over 331 files; bandit 0 across `agentrouter` and `scripts`; mutation gate PASS (0.986
overall, 0 unreviewed survivors); contract unchanged.

**Unchanged and still honest:** `context_band_accuracy` is 0.6667 against the unchanged
0.90 gate. The RC remains NOT RELEASE READY, and only the two-real-human annotation round
can change that.

## Iteration 27 — 2026-08-09 — TASK-018A versioned API contract + SDK compatibility

**Goal:** the REST API is a product surface with two published SDKs, and nothing stopped a
refactor from renaming a response field, tightening a request constraint or dropping
authentication on an endpoint. `GET /openapi.json` describes whatever the process happens to
serve, so the API could not detect its own regression.

**Built:** a committed, byte-stable contract at `contracts/http/v1/openapi.json` with its
provenance in a sibling `manifest.json` (so an unchanged API produces an unchanged file), a
semantic checker that classifies every change as breaking / risky / additive, and
`agentrouter contract export|check` — exit `0` compatible, `1` breaking, `3` missing or
untrustworthy baseline. A missing baseline is a failure, never a pass. `export` refuses to
overwrite the baseline while a breaking change is present; accepting one needs
`--accept-breaking --reason` and appends to a history a later export cannot erase. New CI
job `api-compatibility`; `enforce-release-gate` now depends on it.

**The gate was guarding nothing, twice.** Four of nine operations were declared `-> dict`,
so the contract said only "an object" for their responses — a renamed field on `/v1/route`
produced *no diff at all*. And auth was a bare `X-API-Key` header, indistinguishable in the
export from any other optional header, so adding or removing authentication on an endpoint
was invisible. Both are fixed: typed response envelopes with `extra="allow"` (so nothing is
stripped from the wire — verified against live payloads), and a declared `APIKeyHeader`
security scheme.

**Two HIGH security findings on the existing server, both real:**
- `@app.exception_handler(Exception)` was registered on Starlette's *outermost* middleware,
  above the request-id middleware, so it never ran. An unhandled fault was answered by
  `ServerErrorMiddleware` with no error envelope and no `X-Request-ID`. Now converted inside
  `request_id_middleware` — and logged at ERROR with a redacted traceback, because catching
  it there also stops the ASGI server from logging it, which would have traded a leaky 500
  for a silent one.
- The `RegistryError` handler returned `str(exc)`, which interpolates the registry path *and
  the offending YAML source line*. A registry is malformed at exactly the moment somebody has
  pasted a credential into it, so this returned that credential to an unauthenticated caller
  on `/v1/models` and `/ready`. Both now answer `registry_unavailable` with a fixed message;
  the detail goes to the log only.

**A gate you can edit is not a gate.** An unresolvable, self-referential or remote `$ref`
inlined as `{}`, so a one-character edit to the committed baseline made a schema look
permissive and turned CI green — the baseline is now refused outright if it contains one.
`$ref` expansion is bounded (a fan-out document would otherwise OOM), export refuses to
follow a symlink or write outside the repo root, and the acceptance history records only the
changes the checker itself found, so it cannot assert a break that never happened.

**My own test found the next bug.** A 26-level fan-out document took 66 seconds to validate
because `validate_refs` re-walked every path — 2**26 steps on a contract small enough to read
by eye. The check meant to protect CI would have hung it. Memoising validated refs (the DFS
stack still catches cycles) took the contract suite from 66s to 3.5s.

**And one classification bug.** Adding `maxLength` where there was none was reported as
merely "risky", because the comparison treated an absent bound as unknown. An absent bound is
the *unbounded end of the range*, so introducing one rejects every longer request that used
to be valid. It is now the strongest tightening: **breaking**.

**SDK parity is evidence, not a claim.** `contracts/sdk/capabilities.json` lists nine
operations, and every one is exercised against the real app — Python via in-process uvicorn,
TypeScript via `scripts/serve_for_parity.py` over loopback. The TS suite previously only
asserted the requests it *built*, which cannot catch a well-formed request the server
rejects. CI sets `AGENTROUTER_REQUIRE_LIVE=1` so a skipped live suite fails rather than
passing quietly.

**Verification:** 775 passed / 3 skipped; branch coverage 85.32% (gate 80%), `contract.py`
92%; 33 hook tests; ruff check + format clean; bandit 0 with no new `nosec`; pip-audit clean
on both the env and `requirements.txt`; the CI secret scan mirrored locally with 0 findings
outside `tests/`; `pytest -m security` green; wheel + sdist built; **`contract export` from a
clean wheel install in an unrelated directory is byte-identical to the committed contract**;
a core-only install (no `[server]` extra) gives guidance and exit 1 rather than a traceback;
npm typecheck clean and 18/18 TS tests with the live app, 0 skipped. Critical-module mutation
gate re-run locally: **PASS** — overall 0.9858, safety_policy_execution 0.9877, routing_engine
0.9815, 0 unreviewed survivors, no threshold lowered and no new allowlist entry.

**Second review round — the reviewers were right twice more.** PR #9 was already green on
every CI job. That was not treated as evidence.

*Security, 2 HIGH.* `/ready` is unauthenticated **and** rate-limit exempt, and it logged the
registry error at ERROR with a full traceback. Python's `lastResort` handler writes ERROR to
stderr even with no handler configured — so any caller could push ~**8 KB per request** of
registry path, offending source line and any pasted credential into the operator's log, with
no auth and no rate limit. A malformed registry is the user's data being wrong, not a bug, so
it now logs a type and a remedy and nothing else: **8016 → 202 bytes**, no path, no content.
And `_SECRET_RE` turned out to match four vendor prefixes while **16 of 23** real credential
formats walked straight through it — Google, GitLab, Slack, HuggingFace, fine-grained GitHub
PATs, AWS *temporary* keys, JWTs, connection-string passwords. Replaced with a generic
keyword-and-entropy detector that also recurses into non-string values.

*The gate could still be deleted.* `rm contracts/http/v1/openapi.json` turned four breaking
changes into a green build — and my own commit message had claimed the acceptance history was
unerasable, which was false. CI now checks the live app against the contract on the **base
branch**, which the author of a pull request does not control. Fixing that surfaced a second
form of the same hole: `contract export` treated an *unreadable* baseline as an absent one, so
corrupting the file bypassed the refusal that deleting it triggers — exit 0, silent overwrite.

*The checker was still half-blind.* `_compare_schema` never descended into
`anyOf`/`oneOf`/`allOf` — which is exactly what FastAPI emits for **every** optional field, so
the fields the response models were added to protect were guarded for presence only. You could
delete a value from the `risk` enum and CI stayed green. `components.securitySchemes` was never
compared either, so renaming the auth header to `Authorization` was invisible while the
requirement still read `APIKeyHeader`. Both fixed. Three *false reds* were corrected in the
other direction, the important one being a new required **response** field: FastAPI marks every
non-defaulted response field required, so adding a field to `ModelSummary` failed CI and pushed
maintainers toward `--accept-breaking`. `required` is now read per direction — on a request it
is an obligation on the caller, on a response it is a guarantee from the server.

*And I had broken real user data.* Typing the four response models made `/v1/decisions/{id}`
return **500** for any persisted decision whose engine payload had drifted. Decisions are opaque
JSON in SQLite with no schema version, so asserting today's shape over yesterday's data breaks
what the user already has — the one failure a *compatibility* change must not introduce. The
engine-owned fields are `Any` now; their names, which are what the checker protects, are
unchanged.

*Bounds that were not bounds.* `_MAX_EXPANDED_NODES` was allocated per call while the traversal
re-entered it per property, so cost still grew with the API: 73 s from an 11 KB crafted file.
One shared budget on `Report` took that to **0.20 s**, flat from 1 to 256 paths.

*And the scan I widened caught me.* Adding `scripts/` to bandit immediately produced a HIGH
`B613:trojansource` — in my own new sanitising regex, because I had written the bidi ranges as
literal characters. That finding is the argument for the change.

Documentation was corrected rather than defended: AD-5 no longer claims an unerasable history,
AD-6 explains the directional `required` rule, and `docs/API.md` now carries an explicit
**"What the checker still cannot see"** list.

**Final battery:** 821 passed / 3 skipped; coverage 85.29%; 33 hook tests; ruff clean over 316
files; bandit 0 across `agentrouter` **and** `scripts`; pip-audit clean; credential scan clean;
clean-wheel export byte-identical; installed-wheel server smoke correct; 18/18 TS tests against
the live app, 0 skipped, 0 temp dirs leaked.

**Third review round — my own fix was incomplete, and the reviewer caught it.**
`prompt` was still `str | None`, so `/v1/decisions/{id}` *still* returned 500 for a
decision persisted when `prompt` was a dict. I had fixed the fields I thought of and
missed one, which is exactly how this class of bug survives a fix. The rule now admits no
exceptions: every field on a passthrough envelope is `Any`. Nine drift shapes, zero
non-200s.

The same pass found eleven more false greens and seven false reds. The worst were
structural: **`allOf` was treated as a union**, so every `allOf` change was classified
backwards — a conjunction gets *narrower* with more branches, not wider. Introducing an
enum on a free-form request field reported nothing at all, because the comparison required
an enum on *both* sides — and that is the most extreme narrowing there is. `const` was
never compared, though pydantic emits it for every `Literal`. And the enum block turned
out to be the only classifier in the whole function that ignored request-vs-response
direction, contradicting AD-6's own stated principle two files away.

**And the acceptance workflow was a dead end I had built without testing end to end.**
`contract check` never *read* `accepted_breaking_changes` — the field was only ever
written. So `export --accept-breaking` moved the branch baseline and turned the in-branch
check green, while the base-branch check I had added in the previous round still reported
the same break, forever. A breaking change could be formally accepted by the owner and
could never merge. `check` now reads the manifest in the tree under review and downgrades
a break matching a recorded `(kind, location)` to an `accepted` severity: loud, but not
blocking. An unrecorded break in the same change still fails.

Documentation was corrected a second time. AD-6 had justified untyped engine payloads by
claiming the union is all that gets compared — `_unwrap` was added *in the same change* to
make that false. The claim is gone; the reason stands without it.

**One gap, stated plainly:** the independent security re-review hit a session limit before
returning findings. The second-round security fixes have their own regression tests, but
no fresh adversarial security pass ran against this final diff.

**Third-round battery:** 839 passed / 3 skipped; coverage 85.53%; 33 hook tests; ruff
clean; bandit 0 across `agentrouter` and `scripts`; pip-audit clean; clean-wheel export
byte-identical; 18/18 live TS tests, 0 skipped, 0 temp dirs leaked.

**Unchanged and still honest:** `context_band_accuracy` is 0.6667 against the unchanged 0.90
frozen-holdout gate. The RC remains NOT RELEASE READY. Nothing was tagged, published or
deployed; `main` is untouched.

## Iteration 26 — 2026-08-08 — TASK-016 verified host states; mutation gate repaired

**Goal:** close the command.md PHASE C gap — hosts reported only
available/unavailable/unknown, so a first-run user could not tell "CLI not installed" from
"installed but not logged in", and `hosts doctor` offered no recovery action.

**Built:** a readiness `state` (missing / installed / configured / authenticated /
authorized / degraded / unknown) plus a per-host `remedy`. `availability` keeps its exact
prior meaning and is now *derived* from the state, so routing, `execute` gating and
`models list --available` are untouched. `hosts list/doctor/show`, the setup wizard and the
execute refusal all report the state and the fix; `hosts doctor` ends with the cheapest
concrete fix and exits non-zero only when no real host is ready. REST/MCP gained additive
`state`/`remedy` and `host_state`/`host_remedy`. New USER_GUIDE section 8.

**Bug fixed:** detection tested the API-key env var for *truthiness*, so a set-but-blank key
(`OPENAI_API_KEY="   "`) reported **available** and `execute` would target a host that cannot
possibly authenticate. Now `degraded`/unavailable with a fix-it message.

**Honesty:** `authorized` means a real authorization check succeeded. That check is not
implemented (PHASE C lists opt-in live checks separately), so no offline path returns it —
asserted by test. `authenticated` means a credential *exists*, never that it was accepted.

**Security review — 0 critical, 1 HIGH, 1 MEDIUM, 3 LOW, all fixed and regression-tested:**
- *HIGH:* this task introduced the first filesystem access into `detect_host`, and
  `Path.exists()`/`is_dir()` propagate `EACCES`/`ENAMETOOLONG` — so a container or NFS `HOME`
  the user cannot traverse turned `hosts doctor`, `route` **and the REST `/v1/hosts` endpoint**
  into a raw traceback (unhandled 500). Detection could not raise at all before, so this was a
  genuine regression I introduced; now degrades to "no evidence".
- *MEDIUM:* a blank env fallback outranked a working CLI login, so `ANTHROPIC_API_KEY=` plus
  keychain auth reported `degraded` and refused to execute. Evidence is now positive-first.
- *LOW:* registry-controlled `required_command` was echoed unsanitized and could emit ANSI
  escapes to forge an "authenticated" line; a mutation-kill test was non-hermetic (passed only
  because this machine has `~/.codex/auth.json`); "closest fix" was really "first in list order".
- Reviewer verified **zero file opens** during detection, no credential in any output field, and
  an exhaustive **4320-case differential** showing **0 cases more permissive** than before (912
  strictly stricter — all blank-key cases).

**CI repair (the honest kind):** `critical-modules` failed on the first run —
`safety_policy_execution` fell to **0.8895** (target 0.95) with **72 unreviewed survivors**,
because the new code added mutants the suite did not kill. Repaired with **30 exact-value
mutation-killing tests**, not by lowering a threshold or allowlisting anything. Pinning `.host`
on each assertion is what killed the `host -> None` family; one assertion was itself the bug (a
substring check let an `"XX...XX"`-wrapped mutant survive, since the wrapped text still contains
the original — now an exact line match). Reproduced the campaign locally (mutmut 3.6.0, same
runner and flags, 1057 mutants) before pushing: **overall 0.9858, safety_policy_execution
0.9877, routing_engine 0.9815, 0 unreviewed survivors, all five gates PASS.**

**Verified:** 684 passed / 3 skipped; 33 hook tests; ruff + format clean; bandit 0 with no new
`nosec`; pip-audit clean; clean-wheel install outside the repo exercising `hosts doctor/show`,
the blank-key path, the unreadable-`HOME` path and `route`.

**Merged:** PR #7 → RC, merge commit `5847c22`, branch deleted local+remote. Post-merge RC CI
green across CI, Critical Mutation Testing and Security.

## Iteration 25 — 2026-08-08 — TASK-015 trusted catalogs merged; git guardrail repaired

**Goal:** close TASK-013's deferred catalog scope, then land it — which first required
repairing a repo guardrail that made landing anything impossible.

**Built (TASK-015):** file-level `provenance` block on every generated catalog
(provider, source_url, fetched_at UTC, count, tool_version, cli_args) that the registry
loader ignores; atomic refresh via `tempfile.mkstemp` + `os.replace` with cleanup on
failure; candidate-deprecation reporting on refresh (report-only, never auto-deletes);
`rollback` with non-destructive backup rotation plus a new `providers restore`; and a new
`providers doctor` that parses and schema-validates every generated catalog, exiting 3
only on real corruption (a merely stale catalog still reports OK).

**Independent security review of the diff — 0 CRITICAL, 3 MEDIUM, 2 LOW.** All
medium/low fixed, regression-tested, and re-verified against the reviewer's own
reproductions:
- *Predictable temp filename + symlink-following writes* (verified exploitable): a
  pre-planted symlink at the fixed `…tmp<pid>` / `.bak` path redirected a catalog write
  to an out-of-tree file. Fixed with `mkstemp` for the refresh temp file and an
  `O_CREAT|O_EXCL` exclusive create for the backup — neither follows a planted symlink.
- *Crash instead of clean failure*: `doctor`/`status`/`route` raised a raw traceback
  (exit 1) on a non-mapping YAML root or non-UTF-8 bytes, so CI could not distinguish
  "catalog is corrupt" from "the tool broke". Fixed with a typed `CatalogError` +
  `_load_raw`, plus a `registry._load_yaml` `UnicodeDecodeError` catch; all three now
  fail cleanly with exit 3. (The `route` crash was a pre-existing gap, fixed here since
  it is the same corruption class `doctor` exists to catch.)
- *Silent backup loss*: rotation used 1-second granularity and moved over an existing
  name, so two rollbacks in the same second destroyed history — contradicting the
  charter's own acceptance criterion. Fixed with a nanosecond key + collision probe;
  five rapid cycles now keep five distinct backups.
- LOW: provider-id allowlist for `rollback`/`restore` (defense in depth); control
  characters stripped from provenance before it is echoed to a terminal.

**Guardrail repair (explicitly owner-authorized this session):**
`.claude/hooks/pre_tool_guard.py` blocked `git add`/`commit`/`push` unconditionally,
directly contradicting `command.md` §14 ("You may: … commit verified work; push to the
current release/task branch") and the `AGENTS.md` git policy — the repo's own history
(PR #2–#5) could only have been produced by the very operations the hook forbade. Now
branch-aware: add/commit only on `task/*`; push only from a `task/*` branch for that same
branch, never forced, never targeting a protected branch. Direct writes to `main` and
`release/*` stay refused, as do force push, remote-branch deletion, tags, history
rewriting, `reset --hard`, `git clean`, recursive deletes, deployment, publication,
`shell=True`, permission bypass and secret printing. 33 hook tests cover the matrix,
including a bug found while using it — shell redirections (`2>&1`, `> file`) were being
parsed as push refspecs — with a test proving redirection stripping cannot smuggle a
protected target.

**Verified:** 629 passed / 3 skipped; 33 hook tests; ruff check + format clean; bandit 0;
pip-audit no known vulnerabilities; clean-wheel install outside the repo exercising
`providers status/doctor/rollback/restore` and `route` incl. the corrupt-catalog path.

**Merged:** PR #6 → RC, merge commit `8661629`, task branch deleted local+remote.
Post-merge RC CI green (CI matrix, Security, Critical Mutation Testing).

**Next:** TASK-016 verified execution-host states + provider diagnostics/onboarding.

## Iteration 24 — 2026-08-08 — TASK-014: CI release-gate report/enforce split; state docs reconciled

**Goal:** verify and merge PR #5 (TASK-014), reconcile stale project-state docs against real
GitHub state, then open TASK-015.

**PR #5 verification:** all checks green (test 3.10-3.13, test-windows, build-smoke, Security
scan, release-readiness-report); `enforce-release-gate`/`live-smoke` correctly SKIPPED on a
task->RC PR by design. Marked ready for review, merged (merge commit `b62ffd7`), branch deleted
local+remote. Post-merge push CI on the RC head reproduced green with the same skip pattern.

**Environment note:** the working tree initially showed ~169 files "modified" versus HEAD; this
was confirmed byte-for-byte identical content with only CRLF vs LF line endings (`git diff
--ignore-cr-at-eol` showed zero diff; `core.autocrlf` was unset). Not real work — restored to
match HEAD (`git restore .`) before touching any branch operations.

**Local env blocker (recorded in prior iterations) re-checked and resolved:** full `pytest` now
completes in ~18s on this machine (595 passed, 3 skipped); ruff check/format and bandit both
clean. CI remains an independent cross-platform authority but is no longer the only usable
regression signal.

**Docs reconciled:** LOOP_STATE.json, PROJECT_STATUS.md, CODEX_HANDOFF.md, RELEASE_READINESS.md,
QUALITY_DASHBOARD.md, loop/BACKLOG.yaml, and `status:` fields on TASK-011/012/013/014 task.yaml
files — all updated from "TASK-011 merged" (iter21 snapshot) to the current true state
(TASK-011/012/013/014 all merged; RC @ `b62ffd7`). loop/BACKLOG.yaml's L1/L2/L3/L5/L6/L7 entries
were stale duplicates of already-done TASK-001/002/003/005/006/007 — moved to `done`; L4
(classifier tuning) marked superseded by the TASK-009 proven ceiling + TASK-011/012 data program.

**Next:** TASK-015 trusted catalogs (provenance block, deprecation reconciliation, atomic
refresh, rollback hardening, provider doctor/status), extending TASK-013's deferred scope.

## Iteration 23 — 2026-08-01 — TASK-013: catalog freshness status + rollback

**Goal:** make dynamic provider catalogs trustworthy and reversible — freshness/staleness
reporting and a safe rollback, on top of the existing `refresh.py`, without changing routing
behavior or manual-wins semantics.

**Built:** `agentrouter/catalog_ops.py` (offline, read-only except rollback) —
`read_status`/`list_generated` (freshness of each `models.<provider>.generated.yaml` judged
against `registry.STALE_AFTER_DAYS`) and `rollback` (backup-then-remove one generated file;
manual `models.yaml` untouched so routing reverts cleanly). CLI: `agentrouter providers status`
and `agentrouter providers rollback <provider>`. `tests/test_catalog_ops.py` (9 tests).

**Deferred (this increment, to keep it low-risk and independently verifiable):** a structured
file-level `provenance` block in `write_generated_registry` and deprecation reconciliation
(models present in the generated file but gone from the live catalog, reported on refresh).
Picked up by TASK-015.

**Merged:** PR #4, merge commit `c8fe429`, branch deleted local+remote.

## Iteration 22 — 2026-08-01 — TASK-012: human annotation operations

**Goal:** build blinded annotation packs for two real annotators + adjudication over the
63-candidate pool from TASK-011, producing the human-labelled dev set + new private holdout that
is the only honest path to closing the release-gate.

**Built:** `agentrouter/annotation/packs.py` + `agentrouter dataset {pack,progress,export,
adjudication-pack}`; a resumable `annotate` flow (per-item save; clean Ctrl-C/EOF pause);
blinded independent packs (randomized order, no cross-visibility, no rule/model predictions, no
frozen-holdout labels); disagreements-only adjudication pack with no auto-adjudication; JSONL+CSV
export. Operator docs: `ANNOTATOR_A_INSTRUCTIONS.md`, `ANNOTATOR_B_INSTRUCTIONS.md`,
`ADJUDICATOR_INSTRUCTIONS.md`, `TASK_012_OWNER_ACTIONS.md`.

**Merged:** PR #3, merge commit `0ddf401`, branch deleted local+remote. The real two-person
labeling round remains an external/owner step.

## Iteration 19 — 2026-07-31 — TASK-009 decision A: learned context-band classifier + proven ceiling

**Goal (decision A):** build a principled dev-only learned context-band classifier, compare
rules / learned / hybrid, evaluate the frozen holdout exactly once, and either pass the 0.90
gate honestly or prove a technical ceiling. Full graph-aware loop; no holdout tuning.

**Built:** `agentrouter/context_model.py` — multinomial logistic regression over 14 interpretable
regex features, trained **dev-only** (LOOCV 0.9583, C=1.0). Runtime inference is **pure Python**
(softmax over JSON weights) — no sklearn, no network, deterministic. One shared feature extractor
for train + serve (no skew). Artifact `agentrouter/benchmarks/context_band_model_v1.json` packaged
in the wheel; verified loading + predicting from a fresh `pip install`.

**Frozen holdout — evaluated ONCE, 3 configs, config fixed a priori:**

| config | acc | 95% CI | macro-F1 | recall S/M/L |
|--------|:---:|:------:|:--------:|:------------:|
| rules-only (SHIPPED) | 0.6667 | [0.521,0.786] | **0.6792** | 0.733/**0.600**/0.667 |
| learned-only | 0.6889 | [0.543,0.805] | 0.6613 | 0.800/0.333/0.933 |
| hybrid(0.45) | 0.6444 | [0.498,0.768] | 0.6188 | 0.667/0.333/0.933 |

**Finding:** none reach 0.90. Learned's +0.022 accuracy is not significant (overlapping CIs) and
comes with a *lower* macro-F1 — it lifts large recall but collapses medium recall 0.60→0.33.
Hybrid is worst. **Proven ceiling:** 24 dev cases underdetermine the medium/large boundary;
closing to 0.90 honestly needs a larger human-labeled dev set or real-file signals, not more
hand-rules or holdout tuning.

**Decision:** ship **rules-active** (`_USE_LEARNED_BAND=False`) — best macro-F1, balanced recall,
explainable. Learned model retained as a tested, flag-gated artifact with rule fallback; no runtime
cost while disabled. Study: `loop/tasks/TASK-009-context-band-holdout/learned-model-study.md`.

**Verify:** `pytest -q` → 481 collected, **480 passed** + 1 env-skip (otel), incl **7** new
`test_context_model.py`. ruff clean, bandit **0** (under `-c pyproject.toml`). `eval run --all` →
grade **98.23**, **6/7 gates PASS**, context_band **FAIL** 0.6667 (honest ceiling). Clean-wheel
verified. Graphify post-impl 2309 nodes / 4319 edges; `context_model.py` is a leaf module, **no
cycle**. (One pre-existing plugin backup test is order-flaky on Windows — passes isolated,
unrelated to TASK-009.)

**Independent gates:** release-auditor → **FAIL-to-release / correctly HELD** (all claims
reproduced; safe to hold unpushed pending owner authorization). security-reviewer-arros → no
CRITICAL/HIGH; one **LOW** fixed — `load_model()` now catches `TypeError` to honor the "any error
→ None" contract, covered by `test_malformed_model_returns_none`. Reconciled stale
`loop/QUALITY_GATES.yaml` (0.5778→0.6667, grade 98.32→98.23).

**Not pushed / not released** — the context_band gate is failing; owner authorization required to
push the RC with a failing gate. Remaining blockers are owner/external only.

## Iteration 18b — 2026-07-20 — TASK-008/010 re-audit, Graphify activation, autonomy codified

**TASK-008 independent re-audit — PASS (no repair):** 49 plugin tests pass; live sandbox
install/uninstall/reinstall cycle verified — managed file removed, empty owned dir removed
("removed (empty directory)"), non-empty dir preserved, unrelated user file preserved, idempotent,
state dir cleaned. Codex's `cleanup_dirs` + identity-verified `_remove_owned_empty_directory` fully
close the earlier "empty dir left behind" finding.

**TASK-010 local validation — PASS (CI score still pending push):** `.github/workflows/mutation.yml`
valid YAML; `[tool.mutmut]` targets the 6 critical modules; allowlist valid; `scripts/run_mutation_ci.py`
fails CLEARLY on non-Linux (exit 2, `environment_failure`) and has distinct 0/1/2 exit codes,
0.95 critical / 0.85 broader gates, survivor-allowlist rationale enforcement; 8 harness unit tests
pass. Real mutmut score is genuinely CI-only (Linux/push) — no WSL touched.

**Graphify activated:** official `graphifyy` 0.9.30 (uv tool, isolated) confirmed as the `graphify`
binary. Built graph via CLI (`graphify update .`): 2271 nodes / 4262 links / 238 communities / 281
files. Validated: all production modules present; relations include calls/imports/inherits/extends;
**0 excluded-dir leaks, 0 secrets**; queries (`explain`/`path`) return real source locations.
`docs/GRAPHIFY.md` + `docs/GRAPHIFY_BASELINE.md` written. `graphify-out/` gitignored; `.claudeignore`
added. No global `.claude` skill install (CLI-direct) — existing hooks/agents/skills untouched.

**Autonomy codified:** AGENTS.md, command.md, and the production-loop SKILL now state that routine,
reversible, local, no-cost tasks auto-continue with no owner confirmation, and enumerate the
owner-only actions (RC push while a gate fails, merge, publish, deploy, paid, credentials, destructive).

**Verify:** 473 passed / 1 skipped; ruff clean; bandit 0; graph validated; graphify-out gitignored.
**Git:** none.

**Terminal for this run:** local backlog is exhausted to the honest limit. The context_band held-out
gate (0.6667 < 0.90) is a genuine quality gap whose closure needs a learned classifier or a larger
labeled dev set (blind hand-rules have plateaued; further tuning would game the frozen holdout).
That, plus the RC push (gated on the failing gate) and Phases B-J, are owner/external-blocked.

## Iteration 18 — 2026-07-20 — command.md takeover: baseline reproduce + TASK-009 honest generalization

**Preserve/reconstruct:** inspected working tree (no destructive ops). Confirmed Codex v0.5-rc
state: TASK-008/009/010 artifacts present, `context_band_dev_v1.yaml` (24) + `context_band_holdout_v1.yaml` (45 frozen).

**Graphify provenance (was flagged):** `pip show graphifyy/graphify` both absent, but `uv tool list`
shows official **graphifyy v0.9.30** providing `graphify` + `graphify-mcp` in an isolated uv
tool env. Installed binary IS the official package; safe. No reinstall.

**Baseline reproduced (no trusting claims):** pytest 473 passed / 1 skipped (env-only otel);
ruff + format clean; bandit found 1 NEW Low (B311 `random` in `evaluation/context_bands.py`
bootstrap CI) -> justified with `# nosec B311` (deterministic resampling, not crypto) -> bandit 0.
eval 98.32, Release-ready NO (context_band held-out gate fails).

**TASK-009 honest generalization (owner-chosen path; dev-set only, no holdout tuning):** the
context-band predictor collapsed paraphrased mediums to `small` (holdout medium recall 0.267).
Added to `classifier.py`: broadened act-on-existing verb matcher (`M_ACT_ON_EXISTING`) and a general
definite/possessive+artifact-noun detector (`_DEFINITE_EXISTING_RE`) — "the/its <artifact>" = existing
(medium), "a/an <artifact>" = new (small). Decided from dev + English, measured holdout ONCE.
Result: **holdout 0.5778 -> 0.6667 acc, macro-F1 0.5739 -> 0.6792**, medium recall 0.267 -> 0.60;
DEV stays 1.0; other 6 eval gates still PASS; grade 98.32 -> 98.23. Still below the frozen 0.90 gate:
documented as a genuine generalization gap — closing it blind to the holdout needs a learned model
or a larger dev set, not more hand-rules (would be holdout-gaming, forbidden by command.md §8).

**Verify:** 473 passed / 1 skipped; ruff clean; bandit 0; eval 6/7 gates PASS, context_band FAIL (honest).
**Git:** none this iteration.

**Remaining locally actionable:** TASK-008 independent re-audit (Codex: 48 focused pass), TASK-010
real Linux mutation CI run (needs push), release/agentrouter-v0.5-rc1 branch + CI repair (owner-facing).

---

## Iteration 17 — 2026-07-19 — §10 product audit + repair (audit-driven)

**Audit:** ran the due §10 product audit (4 independent reviewers: architecture,
security, verification, customer) against the uncommitted TASK-001..007 tree. Report:
`loop/reports/audit-2026-07-19/report.md`.

**Findings:** 1 CRITICAL, 6 HIGH, 6 MEDIUM, 4 LOW. The CRITICAL: eval data
(`benchmarks/`, `evaluation/fixtures/`) lived outside the package and resolved via
`__file__…parents[3]`, so `eval run`/`evaluate` were **completely broken on a real pip
install**. Fixed by moving data under `agentrouter/` + `importlib.resources` loading +
package-data; verified in a fresh venv from a non-repo cwd (`eval run --all` = 98.32, YES).

**Repair (every locally-actionable finding):** eval packaging; `--prohibit-tool` typo
validation; `server`/`mcp --help` bracket escape; em-dashes → ASCII in prints + `--help`;
`__version__` from metadata; constant-time API-key note; `init --force` catalog backup;
`_execution_route` dedup into `hosts.execution_route_block`; 404 error-envelope; dead-code
`setup` host warning; release.yml tag-injection → env var; Python-floor docs reconciled to
3.10; context-band overfit + mutation-mechanism docs corrected; UPGRADING uninstall section;
examples/CHANGELOG/PRODUCT_SCENARIOS corrections. Two items not code-changed: 503 registry
path (accepted, local-first), `service.py:143` int() (false positive — unreachable).

**Re-audit:** complete audit re-run → **4/4 PASS** (customer went PARTIAL→PASS after the
`--help` em-dash + dead-code fixes). `pytest` 426 passed / 1 skipped (env-only otel skip);
ruff/format/bandit clean; wheel packages benchmarks + fixtures.

**Still blocked (external/owner):** mutation score (Linux-CI/WSL — no Linux userland here),
P1/P2/P5/P11/P13–15. Follow-ups: empty-dir on plugin uninstall; held-out paraphrases for
context-band gold.

**Verify:** 426 passed / 1 skipped; eval 98.32 (7/7 gates); bandit 0; fresh-venv pip smoke PASS.
**Git:** none — working-tree fixes only, not committed or pushed (per instruction).

---

## Iteration 16 — 2026-07-18 — TASK-007: SBOM + provenance + upgrade guide (L7)

**Implement (docs + CI config, reuse existing release flow):** extended
`.github/workflows/release.yml` — the build job generates a **CycloneDX SBOM**
(`cyclonedx-py environment`), attaches it to the GitHub Release (`gh release upload`), and
attests **SLSA build provenance** (`actions/attest-build-provenance@v1`, OIDC — no secret);
SBOM uploaded as a SEPARATE artifact so the publish job's `dist/` stays PyPI-clean. Added a
`[sbom]` extra, a new **UPGRADING.md** (SemVer policy, upgrade/downgrade, `init --force`
config/registry migration, `gh attestation verify`), a RELEASE.md supply-chain section, and
`.gitignore` for `*.cdx.json`.

**Self-caught bug:** used `--outfile` (unrecognized) → fixed to `--output-file` (verified via
`--help` + a live run producing a 127-component CycloneDX 1.6 doc).

**Independent verification — all 5 items PASS:** workflows valid YAML; SBOM command proven;
`dist/` isolation correct; workflow permissions minimal (`contents`/`id-token`/`attestations:
write`); `github.event.release.tag_name` is the right trigger context; UPGRADING.md accurate
vs `cli.py`; python suite 426 (untouched). Flagged a **pre-existing** CHANGELOG/pyproject
Python-floor drift (3.11 vs 3.10) as an owner decision → KNOWN_LIMITATIONS.

**Verify:** workflows valid; SBOM cmd → CycloneDX 1.6/127 components; `pytest -q` → **426**.
**Git:** none.

## Milestone — all unblocked local backlog complete (L1–L7)
7 tasks done (6 full + L5 partial: mutation env-blocked). 7/7 eval gates PASS, grade 98.32,
Release-ready: YES. **A §10 product audit is now due** before any release claim. Everything
else is external/owner-blocked (P1/P2/P5/P11/P13–15). Stop state: **BLOCKED_EXTERNAL**.

---

## Iteration 15 — 2026-07-18 — TASK-006: TypeScript SDK (contract-parity) (L3)

**Implement (zero runtime deps):** NEW `sdk/typescript/` — `src/index.ts` (`AgentRouterClient`
+ `AgentRouterError` + types) mirroring `agentrouter/sdk.py` exactly: 9 endpoints, same
error envelope, same `_clean` semantics. Node >= 22 (global `fetch` + native TS
type-stripping → no build step). `package.json`/`tsconfig.json`/`README.md`; dev-only
deps typescript + @types/node. `.gitignore` gains `node_modules/`.

**Independent verification (all 5 criteria PASS):** method-by-method parity table vs sdk.py
+ the FastAPI route table — all 9 match; body-cleaning parity; error contract; X-API-Key;
trailing-slash strip. Tests judged meaningful (mock-fetch asserts method/url/body/headers).

**2 parity bugs found + fixed:**
1. (self-caught) `route()` must always send `no_log:false` (Python default False, kept by
   `_clean`) — TS had defaulted it to undefined → dropped. Fixed `?? false`. Also fixed the
   npm test script (`test/*.test.ts` — the directory form dropped the strip-types flag).
2. (verification) a non-JSON error body (proxy/gateway 502 HTML) crashed the TS client with
   `SyntaxError` before the error path; Python guards with `try/except ValueError`. Fixed:
   wrap `JSON.parse` in try/catch → `{}`. Regression test added.

**Verify:** `tsc --noEmit` clean; `npm test` → **8/8**; `pytest -q` → **426** (Python
untouched). Closes the `typescript_sdk` gate. **Git:** none. Remaining local: L7 SBOM/provenance.

---

## Iteration 14 — 2026-07-18 — TASK-005: MCP server (safe read/route/explain) (L2)

**Implement (thin adapter, reuse service.py):** NEW `agentrouter/mcp_server.py` — FastMCP
server exposing `route`/`classify`/`explain`/`list_models`/`list_hosts` over stdio. **No
execute tool** (dry-run only). `agentrouter mcp` command; optional `[mcp]` extra (lazy import);
README "MCP server" section with mcpServers registration JSON.

**Independent audit:**
- security-reviewer-arros: **PASS**, no CRITICAL/HIGH, bandit 0. Confirmed no MCP tool
  reaches a subprocess (execute_dry_run/save_feedback deliberately unexposed); decision_id
  is int-coerced + parameterized (no injection); explain returns caller's own local data.
- verification-engineer: 4/5 PASS; **FAIL crit-4** — `import agentrouter.mcp_server`
  transitively hard-required fastapi via `server/__init__.py`'s eager `from .app import app`,
  so the `[mcp]` extra wasn't self-sufficient.

**Repair:** removed the unused eager re-export from `server/__init__.py` (all callers import
`agentrouter.server.app` directly; the re-export was cargo-cult). First tried a PEP-562 lazy
`__getattr__` but it recursed on the `app` submodule/symbol name clash → deleted the export
instead (ponytail: remove, don't add machinery). Regression test imports mcp_server with
fastapi forced absent.

**Verify:** `pytest -q` → **426 passed** (+8); MCP imports without fastapi; direct app import
still works; ruff clean; bandit 0. **Git:** none. Next local: L3 TypeScript SDK.

---

## Iteration 13 — 2026-07-18 — TASK-004: context-band tuning; last eval gate CLOSED (L4)

**Milestone: all 7 eval gates now PASS** (grade 98.08→**98.32**, Release-ready: YES). The
previously-open beyond-spec `context_band_accuracy` gate went **0.824 → 0.945**.

**Data-driven, anti-overfitting approach.** Per-case gold analysis found two principled
patterns: (1) over-prediction — `M_EXISTING_CODE` words (api/system/project) fired on
reasoning/writing/general prompts; (2) under-prediction — no signal for "operate on an
existing artifact" (review/audit/investigate) or data pipelines.

**Change (classifier.py `_context_tokens` only):** gate the existing-code bump on task_type
∈ {coding, analysis, summarization}; add `M_REVIEW_EXISTING` (review/audit/investigate/
refactor/migrate) and `M_DATA_PIPELINE` (pipeline/etl/ingestion/warehouse/retrieval/vector
db/data validation) → medium. **Deliberately refused** to add fixture-specific keywords
(websocket/billing/oauth2/chat/PII/RFC) for the 9 residual misses — that would be overfitting.

**Audits:**
- product-architect: verdict **PRINCIPLED**; flagged the one fixture-motivated word
  (`documentation`) → **removed in repair**, replaced by the summarization task-type gate.
- verification-engineer: all 4 ACs PASS; regenerated the true 98.08 baseline via git
  worktree — per-dimension diff shows the other 6 gates **byte-identical**, only context
  moved; classify() over all 165 prompts changed **only** context_band (zero task_type/
  risk/approval drift). 418 tests pass; no false positives from new matchers.

**Verify:** `eval run --all` → 7/7 gates PASS, grade 98.32; `pytest -q` → **418 passed**;
ruff clean. **Git:** none. Next local: L2 MCP server.

---

## Iteration 12 — 2026-07-18 — TASK-003: property tests done; mutation env-blocked (L5)

**Property tests (delivered):** NEW `tests/test_property.py` — 6 Hypothesis properties over
classifier invariants (confidence range, enum validity, approval mapping, clarification
flag, --risk precedence, determinism), RateLimiter (`allowed == min(n, limit)`),
IdempotencyCache round-trip, and observability privacy. `pytest.mark.property` +
`importorskip` so hypothesis-less envs skip cleanly.

**Independent verification:** properties are non-vacuous — hand-mutation of production logic
caught 7/8 injected bugs; the 8th (corrupt approval table) exposed a tautological assertion,
**repaired** by asserting against an independent literal → now 8/8. importorskip proven to
skip (not error) in a fresh hypothesis-less venv. Full suite 405 passed.

**Mutation testing — BLOCKED_ENVIRONMENT (root-caused, not looped):** every tool is
incompatible with Windows + Python 3.13 — mutmut 3.x is WSL-only (upstream #397), mutmut 2.x's
pony ORM decompiler crashes on 3.13, mutatest 3.1 crashes on 3.13 (`random.sample` on a set)
and its install downgraded `coverage` (restored). Declared `mutation` extra kept for Linux CI;
real score is a Linux-CI/WSL follow-up. **No score fabricated.** Documented in KNOWN_LIMITATIONS.
Line/branch coverage DOES work: `pytest --cov` → limits.py 95.16%.

**Verify:** `pytest -q` → **405 passed** (+6); ruff+format clean; pyproject net-unchanged
(mutmut config/pins added then reverted after the env finding). **Git:** none.
Next local: L4 classifier context-band tuning.

---

## Iteration 11 — 2026-07-18 — TASK-002: server rate limiting + idempotency (L6)

**Implement (minimal, opt-in, no new deps):** NEW `agentrouter/server/limits.py` —
`RateLimiter` (fixed-window, `AGENTROUTER_RATE_LIMIT`, disabled by default),
`IdempotencyCache` (TTL), both size-bounded (`MAX_ENTRIES`, oldest-first eviction);
`limits_middleware` in `app.py` (429+Retry-After, probes exempt; `Idempotency-Key` POST
replay). Default request path unchanged.

**Independent audit — both agents, neither implemented:**
- verification-engineer: all 4 ACs PASS; idempotency proven at DB level (one decision row);
  fixed-window exact + race-free (32 threads); stores bounded at 50k keys. Found 2 bugs:
  (A) replay dropped Content-Type; (B) 429/replay lacked X-Request-ID.
- security-reviewer-arros: bandit 0; **HIGH** idempotency replay bypassed route auth
  (+ disclosed cached response to unauth callers); **3 MEDIUM** (body not in key -> stale
  replay; non-2xx cached; rate-key trusted rotatable header).

**Repair loop (1 iteration, all resolved):** auth mirrored in middleware + idempotency
gated on `authed` + cache key namespaced by identity + sha256(body); only cache 2xx;
rate-key trusts validated API key else host; cache content-type for replay; reordered
middleware so request-id is outermost. 6 new regression tests for the findings.

**Verify:** `pytest -q` → **399 passed** (+19 this task); ruff+format clean; bandit 0.
**Release:** PASS for TASK-002 (repo stays BLOCKED_EXTERNAL). README "Server limits" section.
Accepted LOW ceilings: duplicate-header collapse (no cookies), per-entry byte budget.
**Git:** none. Next local: L5 mutation/property tests.

---

## Iteration 10 — 2026-07-18 — TASK-001: structured route logging + opt-in OpenTelemetry (L1)

**First task through the new control plane.** Baseline: 371 passed / ruff clean / eval 98.08.

**Discover:** route decisions funnel through `engine.route`, called by `cli.py:417` and
`server/service.py:126`, both building an identical `payload`. Server already had an
`X-Request-ID` middleware; no logging existed elsewhere.

**Implement (minimal, additive):**
- NEW `agentrouter/observability.py` — `log_route_decision`/`route_decision_record`
  (one JSON record on `agentrouter.route`; metadata only, `task_len` not task text),
  `route_span` (opt-in OTel, no-op unless `AGENTROUTER_OTEL` truthy AND otel importable),
  `set/get_request_id` (ContextVar), `configure_logging` (opt-in via `AGENTROUTER_LOG`).
- Wired into `cli.route`, `server/service.route_task`, `server/app` middleware.
- `pyproject.toml` `[otel]` optional extra. README "Observability (opt-in)" section.
- **Silent + private by default** → existing CLI output byte-identical, 371 tests unaffected.

**Independent audit (both PASS, neither implemented):**
- verification-engineer: all 4 ACs PASS; 380 passed; byte-identical default stdout;
  40-req/8-thread concurrency → no request-id leak; OTel positive path proven in a scratch
  venv with otel installed; boundary (no-model / --no-log) records valid, no crash.
- security-reviewer-arros: no CRITICAL/HIGH; bandit 0; no secret/PII/injection; guarded
  optional import. Two LOW hardenings applied → contextvar reset in middleware `finally`;
  route_span docstring metadata-only contract.

**Verify:** `pytest -q` → **380 passed** (+9); ruff check+format clean; bandit 0 issues.
**Release:** PASS for TASK-001 (not a product release — repo stays BLOCKED_EXTERNAL).
**Git:** none. Next local: L6 rate-limit/idempotency.

---

## Iteration 9 — 2026-07-18 — Build the command.md loop control plane

**Decision (user-selected):** build the full command.md §2–6 control plane the prior
sessions had skipped (they tracked state in root files only). Ponytail active → each
artifact is minimal-but-functional, no filler.

**Baseline first (STEP 3):** `pytest -q` → **371 passed**; `ruff check` + `ruff format
--check` clean; `agentrouter eval run --all` → **98.08/100**, 6/7 required gates PASS
(only beyond-spec `context_band_accuracy` 0.82 open). Recorded in
`loop/baselines/baseline-2026-07-18.md`.

**Built:**
- `loop/` — README, BACKLOG.yaml (merged §9 + real repo status), QUALITY_GATES.yaml,
  PRODUCT_SCENARIOS.yaml, PLUGIN_SKILL_INVENTORY.yaml, PLUGIN_SKILL_DECISIONS.md,
  tasks/_TEMPLATE (13-file task skeleton), baselines/, reports/skill-evals/, handoffs/.
- `.claude/agents/` — 7 focused, least-privilege project agents (read-only researchers/
  auditors + one worktree-isolated implementer).
- `.claude/skills/` — production-loop, audit-task, release-check, customer-review,
  plugin-skill-audit, resume-loop.
- `.claude/hooks/` — pre_tool_guard (blocks git-write/destructive/deploy/secret/shell=True/
  publish), post_edit_check (ruff on edited py, fails open), stop_gate (blocks READY claims
  without passing evidence), hook_utils. **15 unit tests → all PASS.**
- `.claude/settings.json` (project-local) registers the 3 hooks.
- New root dashboards: QUALITY_DASHBOARD.md, PRODUCTION_READINESS.md.

**Inventory decision (§3):** this is a local-first Python CLI; the marketplace exposes
dozens of irrelevant components. USE = 7 project agents + python-reviewer/security-reviewer
+ python-testing/security-scan/verification-loop + ponytail. DISABLE = railway/vercel/
gmail/etc. MCP, metaswarm:*, gsd:*, vercel:* (rationale in PLUGIN_SKILL_DECISIONS.md).

**No product code changed** — infrastructure only. Status stays **BLOCKED_EXTERNAL**.
TASK-001 (structured logging + opt-in OTel, backlog L1) primed in intake for the next loop.

**Git:** none (no add/commit/push, per command.md).

---

## Iteration 1 — 2026-07-14 — Phase P3 route-control flags

**Start SHA:** 476c51a · **Baseline:** 276 tests passed, ruff clean.

**Slice:** Implement Phase P3 route-control flags (highest-leverage *fully-local*
gap; catalog refresh/host-verify/measured-profiles all need live APIs → blocked
external). Was marked `[ ]` in ASSIGNMENT_B_STATUS.

**Changed:**
- `agentrouter/controls.py` (new) — `RouteControls`, `apply_controls`, `PREFERENCE_WEIGHTS`.
- `agentrouter/engine.py` — `weights_for`/`route` accept optional `prefer`; preference
  vector overrides complexity/context shifts. Backward compatible (default `None`).
- `agentrouter/cli.py` — `route` gains 13 flags + `_resolve_preference`; filter drops
  fold into `excluded` as `control:` reasons; conflicting flags → exit 2.
- `tests/test_route_controls.py` (new) — 15 tests (8 unit + preference sums + 6 CLI).
- `CLI_SPEC.md` — documented the flags.

**Verify (real output):**
- `pytest -q` → **291 passed** (276 + 15).
- `ruff check agentrouter tests` → All checks passed.
- Smoke (fresh seeded home): `--vendor anthropic` → `anthropic/claude-sonnet-5`;
  `--prefer-quality` on "write a haiku" lifted Haiku→Sonnet-5; `--model` pin honored;
  `--exclude-vendor openai` honored; `--max-price 5` → no model (unknown prices excluded,
  honest); conflicting `--prefer-*` → exit 2.

**Backward compat:** empty `RouteControls` returns the input list unchanged; all 276
prior tests still pass; JSON only gains `control:` entries in the existing `excluded` list.

**Decisions:** see ARCHITECTURE_DECISIONS.md AD-1..AD-3.

**Next:** P3 confidence/abstention surface, then P4 tool-taxonomy.

---

## Iteration 2 — 2026-07-14 — Phase P3 confidence & abstention (P3 now COMPLETE)

**Slice:** classification confidence + abstention (the second half of P3).

**Changed:**
- `agentrouter/schema.py` — `Classification` gains `confidence`, `needs_clarification`,
  `alternative_task_type`, `ambiguity_reason` (all defaulted → backward compatible).
- `agentrouter/classifier.py` — `_confidence` + `_task_type_families`; rule-based score
  (strong when one family fires and task isn't terse; weak on fallthrough/competing
  families/very short input). `classify` takes `uncertainty_threshold`
  (`DEFAULT_UNCERTAINTY_THRESHOLD = 0.4`).
- `agentrouter/cli.py` — `route` gains `--uncertainty-threshold`; text output prints a
  `confidence:` line and a "Low confidence …" note with runner-up + reason.
- `tests/test_confidence.py` (new) — 7 tests. `CLI_SPEC.md` documents the flag/fields.

**Verify:** `pytest -q` → **298 passed** (was 291; +7). `ruff check agentrouter tests` clean.
Smoke: "refactor … add unit tests" → confidence 1.0, no clarification; "do it" →
confidence 0.0, `needs_clarification: true`, note shown in text + JSON.

**Backward compat:** new schema fields defaulted; all prior tests pass; JSON additive.

**Decision:** AD-4 (confidence is rule-based, honest about a rule engine's certainty).

**Next:** P8 plugin installer, then P9 setup wizard. See LOOP_STATE.next_action.

---

## Iteration 3 — 2026-07-14 — Phase P8 plugin/skill installer (local slice)

**Slice:** `agentrouter plugin list/install/uninstall/doctor` — install host
integrations (Claude Code skill, Codex AGENTS.md) from bundled package data.

**Changed:**
- `agentrouter/integrations/**` (new) — bundled copies of the Claude Code SKILL.md
  and Codex AGENTS.md payloads (source-of-truth stays under repo-root `integrations/`).
- `pyproject.toml` — `package-data` now ships `integrations/**/*`.
- `agentrouter/plugins.py` (new) — `PLUGINS` registry + `plan/status/install/uninstall`.
  Reversible (backup `<file>.agentrouter-bak`, restored on uninstall), idempotent
  (skip identical), safe (never clobbers a differing user file without `--force`),
  `AGENTROUTER_PLUGIN_ROOT` override for tests/power users.
- `agentrouter/cli.py` — `plugin` sub-app with 4 commands + `--dry-run`/`--force`.
- `tests/test_plugins.py` (new) — 9 tests incl. force→backup→uninstall→restore.

**Verify:** `pytest -q` → **307 passed** (+9). `ruff` clean. Lifecycle smoke on a temp
root: create → idempotent skip → doctor → uninstall (removed) → unknown plugin exit 2.
`python -m build --wheel` → `agentrouter_os-0.4.0-py3-none-any.whl`; confirmed the wheel
contains `agentrouter/integrations/.../SKILL.md` and `.../AGENTS.md` (packaging verified).

**Backward compat:** additive; no existing command changed.

**Not done in P8 (recorded):** MCP server, `/route*` slash-command set, installer shell
script, examples/ templates, Linux CI run of install (Windows verified locally).

**Next:** P9 `agentrouter setup` wizard; then P4 tool-taxonomy (regression-risky).

---

## Iteration 4 — 2026-07-14 — Phase P9 `agentrouter setup` wizard

**Slice:** non-interactive, idempotent onboarding that composes existing pieces.

**Changed:** `agentrouter/cli.py` — `setup` command (privacy note → init → host discovery
with secrets detected by presence only → `--preference` writes weights → sample route →
plugin hint) + `_write_preference`. `tests/test_setup.py` (new, 5 tests, incl. a test that
a set `OPENAI_API_KEY` value never appears in output).

**Verify:** `pytest -q` → **312 passed** (+5). ruff clean. Smoke: `setup --preference cheap`
seeded home, listed hosts, wrote cheap weights, routed sample → Haiku; bad preference → exit 2.
Fixed a Windows console em-dash (`—`→`-`) so output isn't mojibake under cp1252.

---

## Iteration 5 — 2026-07-14 — Phase P4 tool/workload taxonomy

**Slice:** versioned canonical taxonomy + alias-aware eligibility + `--prohibit-tool`.

**Changed:**
- `agentrouter/taxonomy.py` (new) — `TAXONOMY_VERSION`, canonical `TOOLS` (~22 labels incl.
  legacy web/tool-use), equivalence groups (`web≡web-search`, `tool-use≡function-calling`),
  `is_known`/`equivalents`/`satisfied_by`.
- `agentrouter/engine.py` — eligibility uses `taxonomy.satisfied_by` (a superset of exact
  match: never excludes a model that used to match; only adds synonym matches).
- `agentrouter/controls.py` + `cli.py` — `--prohibit-tool` (the *prohibited* half of P4's
  required/optional/prohibited split), equivalence-aware.
- `tests/test_taxonomy.py` (new, 14 tests) incl. a hygiene test that every seed
  `tool_support` label is a known taxonomy member.

**Verify:** `pytest -q` → **326 passed** (+14). ruff clean. All prior classifier regression
tests still pass (alias matching is backward compatible).

**Not done in P4 (recorded):** *optional* tools are not modeled (only required + prohibited);
classifier still emits the legacy label set (deliberate — avoids destabilizing the
classifier regression suite; new labels enter via registries/controls).

**Next:** P10 security-scan wiring, P12 examples/docs; P6 evaluators + P7 API/SDK largest.

---

## Iteration 6 — 2026-07-14 — Phase P10 security scanning (local slice)

**Slice:** wire Bandit + pip-audit + secret scan; fix the one real finding at root.

**Changed:**
- `agentrouter/refresh.py` — **root-cause fix**: `_http_get_json` now rejects any
  non-http(s) URL scheme before `urlopen` (blocks a malicious/typo'd registry URL from
  reaching `file://`/custom handlers — SSRF / local-file read). Bandit B310 addressed by
  the guard + justified `# nosec`.
- `agentrouter/cli.py`, `agentrouter/evaluation/runner.py` — justified `# nosec B603/B607`
  on the deliberate argv/`shell=False` subprocess calls (injection-tested).
- `pyproject.toml` — `[tool.bandit]` skips informational B404.
- `.github/workflows/security.yml` (new) — bandit (fails on any finding), pip-audit,
  `pytest -m security`, and a committed-secret grep scan.
- `tests/test_security_scan.py` (new, 5 params) — asserts the scheme guard rejects
  file/ftp/gopher/data URLs without touching the network.

**Verify:** `bandit -c pyproject.toml -r agentrouter` → **No issues identified**.
`pip-audit -r requirements.txt` → **No known vulnerabilities**. `pytest -q` → **331 passed**
(+5). ruff check + `ruff format --check` clean.

**Not done in P10 (recorded):** structured logging/OpenTelemetry, mutation testing (mutmut),
Hypothesis property suite, full threat-model doc expansion, metrics/observability.

**Next:** P12 examples/ + README quickstart; P6 evaluators + P7 API/SDK remain largest.

---

## Iteration 7 — 2026-07-14 — P12 docs + P7 API/SDK + P6 evaluators (parallel build)

**P12 (docs, solo):** `examples/README.md` (8 verified scenarios); README quickstart now
shows `agentrouter setup`, `plugin install`, and the P3/P4 route-control flags + confidence.

**P7 (API/SDK) and P6 (evaluators) built by two parallel subagents on disjoint files**
(command.md §6; builder ≠ sole reviewer — I re-verified the merged tree independently).

**P7 — local REST API + Python SDK** (`agentrouter/server/{__init__,app,service,schemas}.py`,
`agentrouter/sdk.py`, `tests/test_server.py`, `tests/test_sdk.py`, `docs/API.md`):
9 endpoints under `/v1` (health, ready, models, hosts, classify, route+persist, decisions/{id},
feedback, execute/dry-run), request-id middleware, optional `X-API-Key` auth, auto OpenAPI at
`/docs`. **No remote execution** — only `/v1/execute/dry-run` returning an argv plan
(`would_execute:false`), asserted by test. 27 new tests.

**P6 — full 100-point evaluator** (`agentrouter/evaluation/evaluators/*.py` + `grading.py`
`measure_all` opt-in + `docs/EVALUATORS.md` + `tests/evaluation/test_evaluators.py`):
routing/safety/platform/provider/feedback/performance evaluators, each a real measurement
(routing partly proxy, declared). Additive gates `high_risk_gated==1.00`,
`synthetic_routing_top1>=0.90`; no existing gate weakened; default `grade()` path byte-identical.
13 new tests.

**Integration (solo):** wired `agentrouter server` command (lazy uvicorn, guarded import),
threaded `measure_all` through `runner.run` → `grade()`, added `eval run --all`.

**Verify (independent, post-merge):** `pytest -q` → **371 passed** (+40). ruff check + format
clean. bandit `-c pyproject.toml -r agentrouter` → **0 issues** (incl. server). Server boots,
`/health` + `/openapi.json` → 200. `eval run --all` → **grade 96.89/100**, 2 gates honestly
FAIL on fixtures (context-band acc, high-risk-gated) → correctly reported NOT release-ready.
`python -m build` → wheel 0.4.0 includes server/sdk/evaluators subpackages.

**Blocked-external (unchanged):** P1 live catalogs, P2 live host verify, P5 measured profiles,
P11 hosted deploy + marketplace, P13/P14 real-beta gates.

---

## Iteration 8 — 2026-07-14 — Fix failing eval gates (root-cause)

**Issue 1 — `high_risk_gated` FAIL (bug):** the safety evaluator treated gold
`risk: [medium, high]` as *requiring* high, so a valid `medium` prediction counted as a
miss (contradicting classification `high_risk_recall==1.00`). Root cause: `_gold_high_risk`
used `Level.high in risks`. **Fix:** mandatory-high only when `must_require_human_approval`
or `set(risks) == {high}` (high is the *sole* acceptable value). Now 24 cases, all gated →
gate **1.00**. Not a weakening — corrects "acceptable set" vs "required" semantics.

**Issue 2 — `context_band_accuracy` 0.76 (real classifier gap):** medium-context recall was
0.30 — coding/review tasks on an *existing* component ("add pagination to the products
endpoint", "the auth package") were scored as 2k-token small. **Fix:** `M_EXISTING_CODE`
signal in `_context_tokens` → tasks referencing existing components/APIs/PRs get medium
(12k). Accuracy 0.76→**0.82**, medium recall 0.30→0.67, macro-F1 0.756→0.862. Did NOT chase
0.90 (one-line-prompt band inference has a natural ceiling; forcing it = overfitting). This
gate is beyond command.md's P13 set.

**Also:** tightened routing gate `>=0.90`→`>=0.95` to match command.md P13 exactly (value 1.0,
declared proxy); updated its test + docs.

**Verify:** `pytest -q` → **371 passed** (classifier change broke nothing). ruff+format clean,
bandit 0. `eval run --all` → grade **98.08**; **all command.md-required gates PASS**; only the
beyond-spec context-band check remains <0.90 (0.82), documented.
# Current-status correction — 2026-07-20 — Codex takeover

Historical entries below accurately record what was believed and measured in those
iterations, but their release-readiness conclusions are superseded. The former
0.945 context-band result is in-sample gold-set accuracy. The new frozen 45-case
holdout measures 0.5778 accuracy (95% CI 0.4330–0.7103), so canonical evaluation is
98.32/100 with 6/7 gates passing and release readiness **NO**. A real Linux mutation
score and release-branch GitHub checks are also pending. Current state lives in
`LOOP_STATE.json`, `QUALITY_DASHBOARD.md`, and `RELEASE_READINESS.md`.

## 2026-07-31 — iter20: RC branch published (owner-authorized, gate failing)

- Owner authorized pushing `release/agentrouter-v0.5-rc1` with the failing
  `context_band_accuracy` 0.6667 < 0.90 gate; branch is NOT RELEASE READY by design.
- Secret/generated-file audit: 356 files scanned, 0 secret hits, no tracked `.env`;
  graphify-out/, artifacts/mutation/, dist/ confirmed gitignored.
- Checkpoint commit of all verified inherited work; push; first real Linux
  mutation CI; repair GitHub checks except the honest context-band gate.
- Next: TASK-011 context-band data + annotation program (new dev set + private
  holdout; no reuse/tuning of frozen holdout).

## 2026-07-31 — iter21: TASK-011 merged to RC; mutation gate closed

- **TASK-010b (mutation) CLOSED.** Full Linux campaign (mutmut 3.6.0, 923 mutants):
  overall 0.9837; safety_policy_execution 0.985 (>=0.95); routing_engine 0.9815
  (>=0.85); all gates green; 15 allowlisted-equivalent survivors; no safety/policy/
  execution-bypass survivor. `tests/test_mutation_kills.py` added; `cli.execute()`
  gate logic extracted into an undecorated `_execute()` so mutmut can instrument it.
- **Branch hygiene.** PR #1 closed and `mutation-kill-safety` deleted (fully
  superseded by test_mutation_kills.py — RC passes the mutation gate without it).
- **TASK-011 MERGED to RC** (PR #2 -> merge commit 35e616e; all commits preserved;
  head/remote task branch deleted). Adds the `agentrouter/annotation/` program:
  schema, deterministic unlabelled candidate generation (63 prompts, all ten
  categories, zero frozen-holdout leaks), dedup/near-dup + cross-set leakage,
  two-annotator adjudication, leakage-safe train/dev/holdout splits, versioned
  manifests, rules/learned/hybrid comparison (accuracy/macro-F1/per-band recall/
  bootstrap CI/ECE), optional Graphify impact with text-only fallback, and the
  `agentrouter dataset ...` CLI. 26 annotation tests; full suite 583+ pass;
  clean-wheel verified (packaged candidate pool loads).
- **CI on RC:** test matrix 3.10-3.13 + test-windows + build-smoke + Security +
  Critical Mutation Testing GREEN; only `release-gate` RED (context_band 0.6667 <
  0.90, honest and unchanged). RC remains NOT RELEASE READY. main untouched.
- **Next:** TASK-012 (human annotation operations — blinded packs for two real
  annotators + adjudication) plus parallel locally-actionable engineering.

## 2026-07-31 — iter22: TASK-012 merged to RC (annotation operations)

- **TASK-012 MERGED to RC** (PR #3 -> merge commit 0ddf401; task branch deleted).
  Adds blinded annotation operations so two real annotators can label the
  63-candidate pool independently: `agentrouter/annotation/packs.py` +
  `dataset {pack,progress,export,adjudication-pack}` and a resumable `annotate`
  (per-item save; Ctrl-C/EOF = clean pause). Disagreements-only adjudication pack,
  no auto-adjudication, label-free progress, JSONL+CSV export. Operator docs:
  ANNOTATOR_A/B, ADJUDICATOR, TASK_012_OWNER_ACTIONS (exact commands; two real
  people must label all 63). tests/test_annotation_packs.py.
- CI on the PR: matrix 3.10-3.13 + test-windows + build-smoke + Security +
  Critical Mutation Testing GREEN; only release-gate RED (honest). RC @ 0ddf401.
- Env note: local pytest was killed for multi-second runs this session; CI served
  as the full-suite authority. main untouched; 0.90 gate unchanged.
- **Next:** Phase 3 local engineering — catalog provenance/freshness/deprecation/
  rollback on top of refresh.py.

## 2026-07-31 — iter23: TASK-013 increment merged (catalog freshness + rollback)

- **TASK-013 (increment) MERGED to RC** (PR #4 -> merge commit c8fe429; task branch
  deleted). Additive, no refresh-format/routing/gate change:
  - `agentrouter/catalog_ops.py` — offline freshness (`read_status`/`list_generated`
    from newest entry last_updated vs registry.STALE_AFTER_DAYS) + safe `rollback`
    (.bak then remove one generated file; manual models.yaml untouched).
  - CLI `providers status` and `providers rollback <provider>`.
  - tests/test_catalog_ops.py (9 tests). CI green except honest release-gate.
- Deferred within TASK-013 (follow-up): file-level provenance block in
  write_generated_registry + deprecation reconciliation on refresh (report-only).
- **Next:** TASK-013 follow-up (provenance block + deprecation), then Phase 3
  priority #3 (verified execution-host states).
