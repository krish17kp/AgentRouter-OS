# Codex Handoff - AgentRouter OS

## Live checkpoint — 2026-11-18

TASK-262 aligns `eval prepare --limit` across Python and Rust: full real-source
validation is followed by the shared deterministic seed-0 subset, with 8 Python
real-mode tests passing and the locked Rust workspace/format checks green.
No external dataset was downloaded and no release or deployment gate changed.

TASK-261 validates the current release artifacts: isolated wheel/sdist build,
Twine checks, packaged-asset inspection, website lint/build, and RustSec audit
all pass. Audit status is no vulnerabilities plus the documented unmaintained
`chrono` warning; no deployment state changed.

TASK-260 reconciles the current verification evidence across release and
production documentation: 2,781 Python tests / 7 skips, 893 Rust/Python
compatibility tests / 1 skip, green workspace Rust checks, and the unchanged
98.23/100 gate held only by context-band accuracy. No deployment state changed.

TASK-259 aligns Rust diagnostic-bundle JSON encoding with Python's ASCII
escaping contract, including surrogate pairs for emoji. The focused
diagnostics/bundle selection passes 45 tests with strict Clippy and formatting;
release gates and deployment state are unchanged.

TASK-258 corrects the unified Rust top-level help so prompt generation shows
the implemented `[TASK]`, `--from`, `--tool`, and `--out` options. The focused
help/version compatibility test and formatting pass; this is a help-contract
increment only. Full verification afterward passes 2,781 Python tests with 7
expected skips and 893 Rust/Python compatibility tests with 1 expected skip;
the canonical gate remains held solely by context-band accuracy 0.6667 < 0.90.

TASK-257's complete Rust/Python and Rust CLI compatibility selection passes
893 tests with 1 expected skip; the only warning is the existing non-failing
Starlette/httpx deprecation. The release gate remains held solely by the
frozen context-band accuracy result.

TASK-256 aligns unified Rust registry-backed inspection errors: `hosts` and
`models` list/show now return exit 3 for missing or unreadable registries,
matching Python. Four process regressions pass and strict Clippy is green.

TASK-255 aligns Rust `doctor --bundle` failure messages with Python's public
`Could not write the bundle:` prefix and exit code 2. Diagnostics/bundle
compatibility is green at 45 focused tests; the Rust CLI crate remains 89/89
with strict Clippy and formatting.

TASK-254 aligns Rust `doctor` human-readable output with Python's public text
contract (remedy indentation, failure guidance, warning pluralization, and the
all-clear next step); JSON output is unchanged. Diagnostics compatibility is
18/18 and the Rust CLI crate is 89/89 with strict Clippy and formatting.

TASK-253 fixes a shipping diagnostics bug found by the Rust comparison: Python
now unpacks `load_models()` and reports the actual eight initialized seed models,
matching Rust instead of reporting tuple length `2`. The focused diagnostics
compatibility selection passes 17/17. TASK-252 also makes Rust doctor report
truthy `AGENTROUTER_OTEL` as `OTel on`; broader parity and release blockers are
unchanged.

TASK-252 aligns Rust `doctor --json` observability reporting with the shared
Rust observability crate: truthy `AGENTROUTER_OTEL` now yields `OTel on`.
Diagnostics compatibility passes 16/16; the `agentrouter-cli` crate passes
89/89 with strict Clippy and formatting. Full observability lifecycle parity,
the frozen context-band gate, human evaluation, live credentials, and deploy
approval remain open.

Active release checkout: `/data/AgentRouter-production`, branch
`release/agentrouter-v0.5-rc1`, pushed head `71408b2`. TASK-175 repaired the
hosted Windows diagnostics path-format mismatch and its full matrix is green.
The local branch contains additional verified SDK, reliability,
release-evidence, plugin-safety, website, and packaging slices; those commits
remain unpushed pending authorization while the enforcing gate is failing.
PR #16 is
the only open PR; no reviews or review requests are present. The macOS-only
no-follow path regression is repaired and pushed; the Windows mismatch is
repaired and validated; the current head’s Linux Rust,
MSRV, API compatibility, build smoke, release-readiness report, Website, and
Security checks are green. The only hosted failure is the expected frozen
context-band release gate at 0.6667 < 0.90. Continue the remaining Partial
parity work without changing thresholds or holdout data.

TASK-241 closes the Rust direct route CLI classifier-option gap: overrides,
preference flags, no-log, and preview/availability compatibility options now
match Python. Fifty-one focused route/unified compatibility tests plus the
locked Rust workspace, strict Clippy, formatting, and diff checks pass. Full R4
CLI parity remains open, as do the honest context-band, human evaluation, live
provider, and deployment gates.

TASK-242 re-ran the full Python regression (2,747 passed, 7 skips) and the
canonical release gate. The gate remains `release_ready=false` at 98.23/100
because context-band accuracy is 0.6667 < 0.90; no holdout, threshold, or
evaluation input changed.

TASK-243 repairs direct route error parity: malformed options now produce a
clean exit-2 `Error:` response, registry/configuration failures exit 3, and
runtime storage failures exit 1, all with no JSON. Thirty-six route
compatibility tests and 89 Rust CLI tests pass with strict Clippy, formatting,
and diff checks.

TASK-244 re-ran the complete Rust/Python and Rust CLI compatibility selection:
867 passed, 1 skipped, and no compatibility regression. The sole warning is
the existing Starlette/httpx deprecation notice.

The route CLI surface now also has successful direct and unified `route --help`
responses listing classifier and preference options; the focused route suite is
37 tests and the combined route/unified selection is 58 tests.

TASK-245 adds successful subgroup help for `models list`, `hosts doctor`, and
`providers status`, `registry list`, and provider refresh/rollback/restore; the
combined route/unified compatibility selection is now 65 tests. TASK-246 adds
successful leaf-command help for `init`, `explain`, `feedback`, `stats`,
`prompt`, `doctor`, and `dashboard`, bringing that selection to 72 tests.
The fresh complete Rust/Python and Rust CLI compatibility selection is 883
passed, 1 skipped, with only the existing non-failing Starlette/httpx warning.
TASK-247 aligns unified `explain` with Python's text and `--json` forms and adds
a process regression; the focused unified selection is now 36 tests. The fresh
full compatibility sweep passes 884 tests with 1 expected skip; the existing
Starlette/httpx warning remains non-failing.
TASK-248 adds named `--tool` forwarding and safe `--out PATH` prompt output;
the focused decision/unified selection is now 42 tests. The fresh full sweep
passes 886 tests with 1 expected skip; the existing Starlette/httpx warning
remains non-failing.
TASK-249 adds task-based `prompt generate TASK` with Python-compatible output;
the focused decision/unified selection is now 43 tests. The fresh full sweep
passes 887 tests with 1 expected skip; the existing Starlette/httpx warning
remains non-failing.
TASK-250 adds a restrictive-policy/weighted-config differential for task prompt
generation; the focused decision/unified selection is now 44 tests. A fresh
full sweep passes 888 tests with 1 expected skip; the existing Starlette/httpx
warning remains non-failing.
TASK-251 aligns the unified stored-prompt trailing newline with Python while
preserving direct probe compatibility; the focused decision/unified selection
is now 45 tests. The fresh full sweep passes 889 tests with 1 expected skip;
the existing Starlette/httpx warning remains non-failing.
TASK-223 synchronizes the unified Rust CLI help with the implemented contract
check/diff/export surface and adds a process-level regression. The fresh full
Python suite passes 2,743 tests with 7 expected skips; the full locked Rust
workspace tests, focused 89/89 contract/unified-CLI differential, release
build, strict Clippy, formatting, and cargo audit are green. TASK-178 repairs the Rust evaluation CLI status real-availability column. TASK-177 aligns stable diagnostic-bundle environment metadata while preserving
the secret-safe allowlist. TASK-176 adds a direct `python -m agentrouter` versus Rust unified help/version
differential and advances the inventory to 60/77 Parity, 17 Partial. The
historical TASK-176 Python run was 2,733 passed / 7 skipped; the current
full-suite checkpoint is 2,743 passed / 7 skipped. Rust workspace,
strict Clippy, formatting, Ruff, Bandit, dependency audits, wheel/sdist build,
and clean-wheel smoke are green. The frozen context-band gate remains 0.6667
against 0.90, so the branch is not release-ready. Continue by polling hosted
checks and repairing only reproducible failures; do not merge, tag, publish, or
deploy without fresh owner authorization. Preserve the untracked historical
directory `loop/tasks/TASK-163-registry-parity-audit/`.
TASK-179 repairs the Rust evaluation `prepare` exit contract: one unavailable
dataset returns 1, while `prepare --all` completes the full blocker report with
exit 0, matching Python and never substituting fixtures. The evaluation crate
passes and the direct all-dataset command reports eight external blockers.
TASK-210 adds JSON contracts to Rust evaluation `status` and `prepare`, with
explicit fixture/real booleans and `SKIPPED_EXTERNAL` blocker records. The
focused compatibility suite passes 20/20; real external loaders remain
unavailable and no release-gate claim is changed.
TASK-211 adds the bounded opt-in Hugging Face rows-API loader for five
metadata-oriented adapters. A live Banking77 preparation produced 3,079
normalized records; CLINC150 was rate-limited during a second live probe and
remains an honest external result. LLMRouterBench/TwinRouterBench, Docker/model
runs, annotation, and release gates remain outstanding.
TASK-212 hardens ordinary Rust SQLite opens with `SQLITE_OPEN_NOFOLLOW` and
adds a symlink-leaf regression without changing the capability-pinned Linux
init path. Complete handle-native SQLite initialization and sidecar race
closure remain R4 limitations; focused storage/CLI tests pass.
TASK-224 aligns reliability truncated-response classification with HTTPX, and
TASK-225 aligns the native SDK's corresponding classification. Their focused
differentials, crate/client tests, strict Clippy, formatting, optimized build,
and cargo audit pass. The SDK and reliability rows remain Partial for broader
native lifecycle and phase-specific transport parity.
TASK-226 adds the owner-controlled staging, canary, rollback, provenance, and
database-safety runbook in `docs/DEPLOYMENT_PLAN.md`; website lint/build also
pass. TASK-227 re-runs the current release gate: 165 cases, score 98.23, exit
1, `release_ready: false`, and only the unchanged context-band gate fails at
0.6667 < 0.90. No staging or production deployment has occurred.
TASK-228 rebuilt the current sdist and wheel with `uv build`; `uvx twine check`
passes both artifacts. TASK-230 modernized the license metadata; the rebuilt
artifacts now pass without the prior setuptools deprecation warnings.
TASK-229 installed that wheel into an isolated temporary environment; version,
`init`, and local `route --json` passed without a provider request.
TASK-231 exercised CycloneDX generation locally: the 1.6 SBOM contains 59
components including `agentrouter-os==0.5.0rc1`; release attachment and SLSA
attestation remain owner-controlled workflow steps.
TASK-232 re-ran the complete Python suite: 2,742 passed, 7 expected skips, and
one existing non-failing Starlette/httpx TestClient deprecation warning.
TASK-233 adds `python -m agentrouter.reliability` as a package-level soak
entrypoint; the focused soak/Rust differential suite passes, while native
transport phase taxonomy and broader lifecycle parity remain partial.
The post-change full Python rerun passes 2,743 tests with 7 expected skips.
TASK-234 rebuilt the current wheel/sdist and passed `twine check`; an isolated
wheel smoke verified the new package help entrypoint, version, init, and local
routing.
TASK-235 re-ran the release gate after these changes: 165 cases, 98.23, exit 1,
with only the unchanged context-band gate failing at `0.6667 < 0.90`.
TASK-236 re-ran the 207-dependency Rust audit and website lint/build: no
vulnerability advisories, lint/build green, and only the known unmaintained
chrono warning remains.
TASK-237 fixes Rust evaluation `status` to use fixture-path presence rather
than record count; 22 CLI compatibility tests, Rust evaluation tests, Clippy,
formatting, and diff checks pass.
TASK-238 fixes Rust evaluation `prepare` for unknown dataset names: it now
reports `UNAVAILABLE (adapter not importable)` and returns exit 1 like Python.
TASK-239 fixes guarded Rust execution runtime exits: missing commands and
provider/host transport failures now return exit 1 (`EXIT_RUNTIME`) like Python.
TASK-240 aligns invalid Rust evaluation `validate-dataset` errors with Python's
`Invalid dataset:` prefix and exit code 3.
TASK-213 enforces the Rust MCP legacy initialize lifecycle (`-32002` before
initialize) while retaining stateless modern discovery. Eight Rust MCP tests,
strict Clippy, and the full Python/Rust MCP compatibility test pass; non-stdio
transport and broader lifecycle parity remain partial.
TASK-214 hardens the Rust doctor read-only database check with SQLite
no-follow semantics; a symlinked database now fails closed without touching the
outside target. Focused diagnostics tests and formatting pass.
TASK-215 extends SQLite no-follow protection to Rust diagnostic-bundle
data-shape reads; the symlink regression passes and normal bundle creation is
unchanged.
TASK-216 adds `agentrouter contract export` to the unified Rust CLI. It accepts
`--source`, `--generated-at`, and `--json`, refuses detected breaking surface
changes, and writes through the existing safe exporter. The default source is
the committed Rust OpenAPI artifact; live framework schema parity remains
partial.
TASK-217 changes Rust bundle database size reporting to `symlink_metadata`,
closing the remaining path-following read in that collector. Full SQLite
handle/sidecar parity remains an R4 limitation.
TASK-218 adds `agentrouter contract check --live URL`. It fetches a running
OpenAPI document with a 4 MiB cap, no redirects, no credentials, validates
references, reports the Rust compatibility surface, and accepts
`--baseline PATH` for base-branch comparisons. Manifest-recorded owner
acceptances remain visible as `accepted` without blocking. The local HTTP smoke
matched the committed baseline; Python live generation and hosted approval
remain authoritative.
TASK-219 aligns Rust `contract export` with the owner-acceptance workflow:
routine exports still refuse breaking changes, while
`--accept-breaking --reason TEXT` records the exact current findings and
preserves prior manifest history through the safe writer. Full workspace tests,
strict Clippy, release build, audit, and a temporary CLI acceptance smoke pass.
TASK-220 makes `agentrouter-evaluate`, its `dataset` annotation commands, and
the Rust diagnostics contract path relocatable with `AGENTROUTER_PROJECT_ROOT`
and current-working-directory root discovery before the build-time fallback.
The evaluation suite passes 21/21, annotation 5/5, and diagnostics 15/15;
real external dataset availability remains an explicit blocker when its
requirements are absent.
TASK-221 sets Unix Rust diagnostic-bundle artifacts to private `0600` mode on
the opened capability-bounded file handle. Bundle redaction and no-follow tests
remain green; broader metadata/runtime parity remains Partial.
TASK-222 aligns Rust bundle `generated_at` with Python's six-digit UTC
ISO-8601 `+00:00` representation; focused bundle checks remain green.
TASK-180 aligns context-band human-readable output with Python (bootstrap CI,
Python-style containers, unquoted checksum, signed delta); JSON remains stable.

TASK-181 is locally verified at the unpushed commit `35e44cb`: the Rust SDK's
native ureq transport now applies the configured timeout independently to
connect, read, write, and aggregate request phases. Focused SDK tests pass
10/10, full workspace tests/Clippy/format pass, and SDK parity remains Partial
for native read/write error classification. Do not push this commit while the
enforcing release gate is failing without fresh owner authorization.

TASK-182 is locally verified after TASK-181: Rust reliability now consumes
response bodies before recording status, so truncated bodies become stable
`ReadError`/`ReadTimeout` transport failures. The real loopback truncation
probe, focused reliability tests, Clippy, and formatting pass. The reliability
row remains Partial for broader process/runtime behavior.

TASK-184 adds the matching native SDK loopback regression: a declared-length
truncated response is reported as `ReadError` rather than parsed as an API
result. Focused SDK verification, strict Clippy, formatting, and diff checks
pass. The SDK remains Partial for native read/write phase taxonomy.

TASK-185 fixes a real plugin-doctor safety diagnosis: a symlinked plugin root
now reports an actionable blocked destination instead of claiming the
diagnostic itself is broken. The focused Unix regression and local symlinked
`~/.claude` smoke pass; no linked target is followed.

TASK-186 refreshes website release evidence: ESLint, the TypeScript/Vite
production build, and the production-only npm audit pass. The bundle is built
locally; hosting publication and deployment remain owner-controlled.

TASK-187 verifies Python packaging end-to-end: `uv build` creates the sdist and
wheel, an isolated install reports `0.5.0rc1`, and installed-wheel `init` plus
`route --json` succeed. PyPI publication remains owner-controlled.

TASK-188 re-ran the affected Python/Rust compatibility surfaces in isolation:
SDK, reliability, plugins, and diagnostics total 77 passed in 26.33 seconds.

TASK-189 exercised the declared SBOM path: isolated CycloneDX generation passed
with a valid 1.6 document containing 46 components. The artifact remains local;
release attachment still requires the approved GitHub Release workflow.

TASK-190 adds `registry_api::DatasetAdapter`, a concrete Rust facade for the
shared adapter lifecycle (metadata, availability, load, prepare, sample,
validate, checksum, describe). Focused facade tests and strict Rust checks pass.
Real HuggingFace loading remains explicitly unavailable and no parity promotion
claim is made. Continue with the next Partial module while preserving the
untracked historical `loop/tasks/TASK-163-registry-parity-audit/` directory.

TASK-191 adds fail-closed MCP regressions for malformed JSON-RPC requests and
invalid tool arguments. The five safe tools remain unchanged; broader MCP
transport/lifecycle parity remains Partial.

TASK-192 re-ran the complete isolated Python suite from this checkout: 2,735
passed, 7 skipped, one existing Starlette/httpx deprecation warning, in 449.37
seconds. No frozen evaluation data or threshold changed.

TASK-193 re-ran the optimized locked Rust build and audit. The release binary
reports `0.5.0rc1`, help succeeds, and 207 locked dependencies have no
vulnerability advisories; RustSec's one unmaintained `chrono` warning has no
fixed upgrade. Hosted PR #16 is still held by the frozen 0.6667 < 0.90 gate and
owner-controlled review/credential/promotion/deployment gates.

TASK-194 adds ordered lazy callable adapter factories for all eight registered
datasets. The registry/base rows remain Partial only for real external loading
and broader adapter behavior; preserve the untracked TASK-163 audit directory.

TASK-195's optimized binary smoke passes from a fresh isolated home: init,
route, doctor, version, and MCP initialize/tools-list. No credentials or
deployment were used.

TASK-196's adapter/base differential regression passes 17/17 tests across all
five external adapter normalizers and the shared contract. Keep real external
loading explicitly blocked until its runtime and credentials are available.

TASK-197/198 add planning-only Rust boundaries for execution and orchestration.
The execution planner is fail-closed around host availability, approval,
remote policy, and manual handoff; the orchestration planner validates bounded
dependency graphs and deterministic parallel groups with conflict, budget,
tool-allowlist, and idempotency checks. Eight focused tests plus strict Clippy
and formatting pass. Neither
crate executes, dispatches, grants tools, reads credentials, or mutates
workspaces. Continue with separately authorized adapters and runtime
integration; do not promote these planning crates as execution parity.

TASK-199 wires the execution planner into the unified binary as
`agentrouter plan <decision-id> [--json]`. Fresh-home init/route/save/plan
smoke is green and reports `execution_enabled: false`. Continue with the
separately authorized adapter/runtime milestones; this command is intentionally
read-only.

TASK-200 records matched 2,000-iteration pure-routing benchmarks for 10/100/
1,000 synthetic fleets. Optimized Rust is faster at p50 and p95 in this local
Linux run; treat it as comparative evidence only, not a production SLO.

TASK-201 verifies the optimized Rust binary with Python environment variables
removed. Isolated init, saved route, read-only plan, doctor JSON, and MCP
initialize pass. This is a Rust-only runtime check for those surfaces; keep
provider execution and deployment gated.

TASK-202 adds a unified CLI process test for read-only planning. It passes with
the normal and explicit remote/approval flags while asserting
`execution_enabled: false`.

## Storage relocation — 2026-11-15

Active release checkout: `/data/AgentRouter-production` on branch
`release/agentrouter-v0.5-rc1` at pushed head `82babba`. The prior checkout is detached and
preserved at `/home/krish/.codex/worktrees/agentrouter-production/AgentRouter-OS`.
Tracked code/test diffs were verified identical before transfer; untracked TASK-153,
154, and 155 task notes and `/data/agentrouter-recovery/task154.patch` were copied.
Context documents are at `/data/agentrouter-context`. Shared Git metadata and Python
venv remain at `/data/AgentRouter-OS`. New Rust build output points to
`/data/agentrouter-build/target`; source `/data/agentrouter-build/environment.sh`
for that location and `/data/agentrouter-build/tmp` temporary files.

The Python TASK-153 full regression in the previous checkout completed: 2,597 passed,
7 skipped, 1 warning, 501.42s; coverage is 92.004% statement, 87.789% branch,
and 91.034% combined. Log and JSON
coverage evidence are at `/data/agentrouter-build/evidence/`. Investigate skips
before any release claim.

TASK-153 was committed and pushed as `82babba`. TASK-154 then changed the
Python bundle writer to use exclusive final-path creation. Its full regression
passes 2,604/7 with 92.021% statement, 87.833% branch, and 91.058% combined
coverage; focused tests, review, hooks, Bandit, build, and installed-wheel smoke
pass. The shared venv now points at this checkout at version `0.5.0rc1`.

TASK-154 was committed and pushed as `2542e2d`. TASK-155 makes supplied
context-band reports fail closed in Rust rather than falling back to ordinary
classification accuracy. Focused 6/6, evaluation compatibility 40/40, full Rust
workspace, strict Clippy, independent review, and full Python 2,609/7 pass.
Coverage is 92.021% statement, 87.833% branch, and 91.058% combined.

## Current checkpoint — 2026-11-17

TASK-173 hardens Rust diagnostic bundle writes. Bundle parents are created with
no-follow component walking, while artifacts and opt-in database snapshots use
a pinned capability directory with exclusive creation; the
storage layer serializes the committed SQLite image and writes/syncs through a
single opened destination handle. Symlink, hard-link, and directory-swap escape
regressions pass.
Focused bundle/diagnostics checks, Rust bundle tests, and strict Clippy pass.
Bundle remains Partial for complete environment metadata and Windows-specific
differential coverage. Commit `75ac6c7`, inspect hosted checks, then continue
the next Partial module.

TASK-172 tightens diagnostics stable-contract parity. Rust now reports the same
package version, server-extra wording, and contract path summary as Python;
the direct stable-check differential and 41-test diagnostics suite pass with
strict Clippy. Diagnostics remains Partial for runtime-specific and full bundle
field parity. Commit/push this small repair, inspect hosted checks, then
continue the next Partial module.

TASK-171 provider refresh parity is independently clear. Rust refresh uses
no-follow registry traversal, fixed bounded HTTPS transport, Python-compatible
OpenRouter/OpenAI mapping, provenance, deprecation warnings, dry-run, and atomic
generated-file replacement. A feature-gated local fixture seam provides
process-level success/error evidence without exposing a production URL option;
OpenAI key gating and credential redaction are covered. Full Rust workspace/
strict Clippy (including the fixture feature) and Python 2,732/7 pass. Inventory
is 59/77 Parity and 18 Partial. Commit this slice, push the authorized RC
branch, inspect hosted checks, then continue with the next Partial module.

TASK-170 packaged annotation CLI parity is independently clear. Rust embeds the
candidate pool and frozen holdout, prefers checked-out files for development,
and falls back to deterministic embedded bytes for installed binaries. Exact
hash/count evidence and source-independent default-pack fallback tests pass;
annotation CLI/schema compatibility passes 88. Inventory is 58/77 Parity and
19 Partial. Commit/push this slice after the full workspace regression, inspect
hosted checks, then continue the next Partial module.

TASK-169 HTTP application lifecycle parity is independently clear. The API
executable now delegates default-home resolution to the shared OS-aware service
resolver. Process-level differentials cover request IDs on auth/rate/CORS short
circuits, generic malformed-registry responses with one redacted log, and
non-cached validation idempotency responses. Focused HTTP/schema compatibility
passes 114; full Rust workspace/strict Clippy pass; full Python regression
passes 2,731/7. Inventory is 57/77 Parity and 20 Partial. Commit this slice,
then push and inspect hosted checks.

TASK-168 observability parity is independently clear. Rust now provides
task-local request context plus a synchronous setter/scoped guard, opt-in
structured events and route records, bounded strictly redacted API errors,
active OTel spans, and one-record server error paths. Focused observability
tests (9), full Rust workspace/strict Clippy, and Python 2,728/7 pass. The
inventory is 56/77 Parity and 21 Partial. Service errors intentionally retain
bounded message-only evidence when a traceback object is unavailable across
the blocking boundary. Continue with the next Partial module after pushing
the TASK-168 commit and inspecting hosted checks.

TASK-155 was committed and pushed as 613550d. TASK-156 routes one injected
Rust classifier consistently through classification, routing, safety, and
performance. Compatibility passes 42/42 and full Python passes 2,610/7 at
92.021% statement, 87.833% branch, and 91.058% combined coverage. It remains
Partial pending public default grade/runtime discovery in TASK-157.

## Recovery checkpoint — 2026-11-15

Active persistent checkout: `/home/krish/.codex/worktrees/agentrouter-production/AgentRouter-OS`,
starting detached at `c7d8180`. The old `/tmp/agentrouter-rust-next` disappeared;
TASK-153 uncommitted changes are being reconstructed. Preserve all current edits.
Python focused tests pass 88/1, Rust CLI library 75/75 and observability 6/6,
Rust workspace, strict Clippy, Python/Rust differential, independent reviews, build
and installed-wheel smoke pass. The first full Python run failed after disk exhaustion;
no coverage evidence from it is valid. A retry runs with COVERAGE_FILE in /tmp,
CARGO_INCREMENTAL=0; monitor /tmp/agentrouter-task153-retry.log and disk free space.
Next: diagnose any retry failure, record coverage, commit only verified changes.
TASK-154 patch is at /home/krish/.codex/agentrouter-recovery/task154.patch; apply
only after the running suite completes. TASK-155 identifies malformed holdout
fallback; fix and test without weakening gates. Preserve all current edits.
Hosted c7d8180 Rust, security, mutation and website pass; enforcing CI fails its release gate.
Production remains IN_PROGRESS; 29 module parity rows and external gates remain open.

## Previous checkpoint — 2026-11-15

The active RC branch is at pushed head `5af3c55`. Hosted Python, Rust, and
compatibility jobs pass across supported platforms, as do API, build, security,
website, and critical mutation. TASK-152 local Python passes 2,590/5 with
92.052% statement, 87.756% branch, and 91.064% combined coverage; Rust
workspace/Clippy, wheel/sdist, and clean-wheel smoke pass. The sole PR (#16) remains held: frozen
context-band accuracy is 0.6667 < 0.90, and it has no human review. Rust parity
is 48/77 full modules. TASK-152 currently changes shared Rust observability,
opt-in API route records, and logging redaction; commit/push to the authorized
RC, inspect hosted validation, then continue the next Partial row.
Human annotation, paid OpenAI live validation, and production credentials are
listed under Needs Krish in `PRODUCTION_STATUS.md`.

## Previous checkpoint — 2026-11-14

Active branch `release/agentrouter-v0.5-rc1`; latest pushed code is `9a7dc7a`.
TASK-150's arbitrary-precision API response differential and full Linux/Python
3.12 regression pass locally. The suite passes 2,580 tests, 5 skipped, with 92.030% statement, 87.712%
branch, and 91.038% combined coverage. Hosted critical mutation passes 1,706
selected mutants with zero unreviewed survivors. Rust workspace passes Linux,
Windows, and macOS; Linux/macOS Python/Rust compatibility passes. Windows
compatibility and most Python jobs are still running. The PR enforcing gate
fails at frozen context-band accuracy 0.6667 < 0.90. PR #16 is the only open PR
and has no GitHub reviews. Keep the PR held.

TASK-141's SDK/reliability selection, Rust workspace/Clippy, and full Python
regression pass. Current coverage evidence is
[`docs/COVERAGE_REPORT_2026-11-14-TASK-150.md`](docs/COVERAGE_REPORT_2026-11-14-TASK-150.md).
TASK-142 compares every evaluator seed model field and Rust exports against
Python's live `__all__`. TASK-143 makes the Rust full-scorecard CLI discover the
actual sibling CLI surface at runtime. TASK-144 is pushed at `0d3ea70`: both
OpenAI adapters reject non-2xx responses, with 68 focused Python tests and
three Rust unit tests passing locally; offline differential cases cover 300,
302, and 399. Its mutation run failed the survivor-review gate; TASK-146 adds
status boundaries to the selected test suite. TASK-145 is pushed at `d80a6df`
with three complete serialized CLINC150 raw-row differentials; external dataset
fetching remains Partial. SDK, evaluator orchestration, and multiple CLI/API/MCP
modules also remain Partial in `docs/RUST_PARITY_MATRIX.md`.

TASK-146 now rejects missing/malformed OpenAI response statuses; its hosted
critical-mutation run passes with zero unreviewed survivors. TASK-147 bounds
Rust SDK TCP connection setup by the configured timeout and passes SDK
differential plus workspace checks locally. The parity matrix has 48/77 full
modules; 29 remain Partial. Next: finish the hosted matrix, continue the next
parity slice, and keep human evaluation, bounded OpenAI live validation, and
production credentials under **Needs Krish**.

## Historical narrative

> **Relationship to `AGENT_HANDOFF.md`:** `AGENT_HANDOFF.md` is the canonical live
> checkpoint and is authoritative for branch, commit, PR and next-action state.
> This file is the Codex-oriented narrative and may lag. Where the two disagree,
> `AGENT_HANDOFF.md` wins. Do not maintain a third handoff.

Last updated: 2026-08-08 (iter 26 — TASK-016 MERGED to RC; mutation gate repaired)

## Current state (iter 26)

- **Branch topology (authoritative):**
  - `main` — stable, untouched (still `602321a`). Never merge into it without explicit owner approval.
  - `release/agentrouter-v0.5-rc1` — integration branch @ `5847c22`. **NOT RELEASE READY**
    (context_band held-out 0.6667 < 0.90, unchanged). Mutation gate **PASSES**. CI is **green** on
    ordinary pushes/PRs (see below).
  - `task/TASK-011-context-band-data`, `task/TASK-012-annotation-operations`,
    `task/TASK-013-catalog-provenance`, `task/TASK-014-ci-release-semantics`,
    `task/TASK-015-trusted-catalogs` — **all MERGED to RC (PR #2/#3/#4/#5/#6) and DELETED**
    local + remote; all commits preserved via merge commits.
  - `mutation-kill-safety` — **DELETED** (local + remote); PR #1 closed as fully superseded by
    `tests/test_mutation_kills.py`.
- **TASK-011 on the RC:** `agentrouter/annotation/` program — schema, deterministic unlabelled
  candidate generation (63 prompts, all ten categories, zero frozen-holdout leaks), dedup/near-dup
  + cross-set leakage, two-annotator adjudication, leakage-safe train/dev/holdout splits, versioned
  manifests, rules/learned/hybrid comparison, optional Graphify impact (text-only fallback), and the
  `agentrouter dataset ...` CLI. Docs in `docs/CONTEXT_BAND_ANNOTATION.md`.
- **TASK-012 on the RC:** blinded per-annotator packs, resumable annotate flow, disagreements-only
  adjudication pack, JSONL+CSV export. The real two-annotator + adjudicator round is still external
  (`TASK_012_OWNER_ACTIONS.md`) — the only path to closing the honest release-gate.
- **TASK-013 on the RC:** `agentrouter/catalog_ops.py` (freshness/staleness vs
  `registry.STALE_AFTER_DAYS`, safe rollback with `.bak` backup) + `providers status` /
  `providers rollback` CLI.
- **TASK-015 on the RC:** trusted catalogs — generated catalogs carry a `provenance` block
  (source_url, fetched_at UTC, count, tool_version, cli_args) the loader ignores; atomic
  refresh (`tempfile.mkstemp` + `os.replace`); candidate-deprecation reporting on refresh
  (report-only); non-destructive backup rotation + new `providers restore`; new
  `providers doctor` that schema-validates every generated catalog and exits 3 only on real
  corruption. Independent security review: 0 critical / 3 medium / 2 low, all medium+low
  fixed and regression-tested (symlink-race on temp/backup writes, crash-instead-of-clean-fail
  on corrupt catalogs, same-second backup-rotation data loss).
- **TASK-014 on the RC:** split the always-on enforcing `release-gate` into
  `release-readiness-report` (push/PR/dispatch, non-enforcing, honest YES/NO) and
  `enforce-release-gate` (RC->main PR / release tag / explicit dispatch only, full enforcement).
  Ordinary CI is green; promotion stays strictly gated.
- **Mutation (TASK-010b CLOSED):** mutmut 3.6.0, 923 mutants — overall **0.9837**;
  `safety_policy_execution` **0.985** (>=0.95); `routing_engine` **0.9815** (>=0.85); no safety/
  auth/policy/execution-bypass survivor. `cli.execute()` gate logic extracted into undecorated
  `_execute()` for mutmut reach. Local iteration via Docker container `armut`.
- **CI on `5847c22`:** test matrix 3.10-3.13, test-windows, build-smoke, Security,
  `release-readiness-report` and **Critical Mutation Testing** all GREEN;
  `enforce-release-gate`/`live-smoke` correctly SKIP (not run) on task/RC pushes by design.
- **Local env blocker resolved (2026-08-08):** full pytest now runs cleanly on this machine (684
  passed, 3 skipped); 33 hook tests; ruff, bandit and pip-audit clean. No longer CI-only
  for regression evidence.
- **GIT GUARDRAIL REPAIRED (2026-08-08, owner-authorized):** `.claude/hooks/pre_tool_guard.py`
  had blocked `git add`/`commit`/`push` unconditionally, contradicting command.md §14 and the
  AGENTS.md git policy and making this loop impossible to execute. Now branch-aware:
  add/commit only on `task/*`; push only from a `task/*` branch for that same branch, never
  forced, never to a protected branch. **Direct writes to `main` and `release/*` are still
  refused** — record state and land every change through a task branch + PR, not by committing
  on the RC. Force push, remote-branch deletion, tags, history rewriting, `reset --hard`,
  `git clean`, recursive deletes, deployment, publication and secret printing stay blocked.
- **TASK-016 on the RC:** hosts report installed/configured/authenticated/authorized/degraded
  with a concrete remedy (offline, credential-free; existence checks only, never a network call
  or a credential read). `authorized` is never inferred offline — it needs the opt-in live check
  PHASE C lists separately, which is not implemented. Fixed a real bug: a set-but-blank API key
  used to report *available*, so `execute` would target a host that cannot authenticate.
  The critical-module mutation gate failed on the first CI run (safety_policy_execution 0.8895)
  and was repaired to 0.9877 with real tests — no threshold lowered, no mutant allowlisted.
- **Next:** remaining local backlog — benchmark routing infrastructure that needs no paid
  inference, customer docs/examples, observability runbooks, API/SDK compatibility + load
  testing (loop/BACKLOG.yaml L4/L9). Do NOT reuse/tune the frozen holdout; the 0.90 gate is unchanged; RC stays
  NOT RELEASE READY; no RC->main without owner approval.

---

## Historical takeover notes (iter 18-19)

## Repository and Git state

- Path: `D:\Krish\Agentrouteros`
- Remote verified: `origin https://github.com/krish17kp/AgentRouter-OS.git`
- Initial branch: `main` tracking `origin/main`
- Initial HEAD: `602321af91ff298c0d5b59d6d36c24f845557fc1`
- Target authorized branch: `release/agentrouter-v0.5-rc1` (not yet created at this checkpoint)
- `git diff --check` and `git diff --cached --check`: no integrity errors at takeover.

### Inherited index (must not be discarded)

Nine staged renames move packaged evaluation data into the Python package:

- `benchmarks/{classifier_gold_v1,routing_gold_v1}.yaml` -> `agentrouter/benchmarks/`
- Seven `evaluation/fixtures/*.jsonl` files -> `agentrouter/evaluation/fixtures/`

### Inherited unstaged tracked work (must not be discarded)

`.github/workflows/release.yml`, `.gitignore`, `CHANGELOG.md`, `KNOWN_LIMITATIONS.md`,
`LOOP_LOG.md`, `LOOP_STATE.json`, `README.md`, `RELEASE.md`, `TESTING.md`,
`agentrouter/{__init__,classifier,cli,hosts}.py`, evaluation base and seven adapters,
`agentrouter/server/{__init__,app,service}.py`, evaluation report artifacts, `examples/README.md`,
`pyproject.toml`, and three focused tests. Initial unstaged diff: 36 files, 951 insertions and
1,701 deletions (the deletions are primarily regenerated evaluation output).

### Inherited untracked work (must not be discarded)

`.claude/` control-plane reference files; `PRODUCTION_READINESS.md`, `QUALITY_DASHBOARD.md`,
`UPGRADING.md`; `agentrouter/{mcp_server,observability}.py` and
`agentrouter/server/limits.py`; the complete `loop/` control plane and TASK-001..007 evidence;
`sdk/typescript/`; and tests for context bands, MCP, observability, properties, and server limits.
`.mutmut-cache` is untracked generated state and must not be committed.

### Ignored/local state (exclude from commits)

`.env` (contents not read or printed), `.venv/`, `.coverage`, `.hypothesis/`, `.pytest_cache/`,
`.ruff_cache/`, Python caches, `agentrouter_os.egg-info/`, `artifacts/evaluation/current/`, `build/`,
`dist/`, `data/`, and `sdk/typescript/node_modules/`.

## Reconstructed state

Inherited work implements exact model/host routing, route controls, confidence/abstention, tool
taxonomy, plugin installers, setup, structured private-by-default logging and optional OTel,
request IDs, bounded rate limiting/idempotency, local FastAPI/Python SDK, safe MCP read/route tools,
TypeScript SDK, evaluation framework, packaged eval resources, SBOM/provenance release changes,
and prior audit repairs. These remain under independent verification.

Locally actionable work remains, despite stale `BLOCKED_EXTERNAL` flags:

1. TASK-008 safe empty plugin-directory cleanup with path/symlink/user-file protections.
2. TASK-009 genuinely held-out context-band generalization evaluation and leakage detection.
3. Bounded Linux mutation-testing GitHub Actions workflow and a real CI score.
4. Fix baseline formatting drift in three `.claude/hooks` files and any later audit/CI findings.

External/owner-controlled items remain live provider credentials/catalogs, paid model benchmarks,
hosted/team infrastructure, marketplace/PyPI publication, real beta users, production deployment,
and final irreversible product decisions.

## Independently reproduced takeover baseline

- Python: `427 passed` (one Starlette/httpx deprecation warning), 2026-07-20.
- Claude hook/control tests: `15 passed`.
- Ruff lint: clean.
- Ruff format: **FAIL**, would reformat `.claude/hooks/post_edit_check.py`,
  `pre_tool_guard.py`, and `test_hooks.py`.
- Bandit: zero findings; five justified nosec exclusions.
- pip-audit: no known vulnerabilities in `requirements.txt`.
- Evaluation: `98.32/100`, 165 cases, all seven current gates pass.
- TypeScript SDK: `npm ci`, 8/8 tests, typecheck clean.
- Packaging: wheel and sdist build successfully; setuptools emits future license-metadata warnings.
- Clean wheel: fresh Python 3.13 venv, installed wheel with `[server,mcp]`, non-repository cwd;
  import/version, help, init, setup, registry list, hosts list, route, eval list-datasets,
  `eval run --all`, packaged benchmarks/fixtures/plugins, API import, and MCP import all pass.
- Clean-wheel temp evidence path:
  `C:\Users\krish\AppData\Local\Temp\agentrouter-codex-wheel-984c6723ae73494984c5575dd3533ae6`.

## Current next command/task

Iter 19 done (Claude, 2026-07-31 — decision A): built a dev-only LEARNED context-band classifier
(`agentrouter/context_model.py`, multinomial LR, pure-Python runtime, packaged JSON weights) and
evaluated rules / learned / hybrid against the frozen holdout ONCE. **Proven ceiling** — none
reach 0.90: rules 0.6667 (macro-F1 0.6792), learned 0.6889 (macro-F1 0.6613, collapses medium
recall), hybrid 0.6444. Learned is not significantly better than rules and has a lower macro-F1,
so shipped **rules-active** (`_USE_LEARNED_BAND=False`); learned kept as a tested, flag-gated
artifact with rule fallback. Study: `loop/tasks/TASK-009-context-band-holdout/learned-model-study.md`.
Baseline: 481 collected — **480 passed** / 1 env-skip (otel), ruff/format clean, bandit 0, eval
**98.23** Release-ready NO (context_band gate). Graphify post-impl 2309 nodes / 4319 edges,
`context_model.py` leaf, no cycle. Clean-wheel verified (model JSON packaged, loads from fresh
install). Independent gates: release-auditor FAIL-to-release / correctly HELD (all claims
reproduced); security-reviewer no CRITICAL/HIGH, one LOW fixed (`load_model()` TypeError catch).
One plugin backup test is order-flaky on Windows (passes isolated), unrelated to TASK-009.

Iter 18/18b (2026-07-20): TASK-008 re-audited PASS (no repair); TASK-010 locally validated (CI
score pending push); bandit regression fixed; Graphify activated; autonomy codified.

Remaining is owner/external-blocked:
- context_band held-out gate (0.6667 < 0.90) — **PROVEN DATASET CEILING** (rules/learned/hybrid all
  tested). Closing honestly needs a larger human-labeled dev set or real-file context signals, OR an
  owner decision to adjust/justify the gate. Do NOT tune against the frozen holdout.
- release/agentrouter-v0.5-rc1 push — GATED: owner authorization required to push an RC while a
  mandatory gate fails.
- Phases B-J (live catalogs, paid benchmarks, hosted infra, PyPI/marketplace, beta) — external/owner.

Resume/re-verify with:

```console
git status --short --branch
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m agentrouter eval run --all
graphify update .
```

## TASK-157 checkpoint — 2026-11-15

TASK-157 is locally complete on `release/agentrouter-v0.5-rc1`: default Rust
grading loads packaged models and discovers the installed CLI through PATH,
with fail-closed errors. Independent review is clear; focused checks and full
Python regression pass (2,613 passed, 7 skipped, 298.77s). Commit/push this
exact task, inspect CI, then select the next Partial Rust parity task. Do not
claim production readiness: frozen evaluation and external gates remain.

## TASK-158 checkpoint — 2026-11-15

TASK-158 is locally complete on `release/agentrouter-v0.5-rc1`. Rust evaluation
CLI argument/error parity is repaired, as is TASK-157's hosted Ruff failure.
Independent review is clear; focused 43, Rust workspace/Clippy, Ruff, and full
Python 2,626/7 pass. Commit/push this exact diff, inspect hosted CI, then select
the next Partial Rust parity task. Production readiness remains held.

## TASK-159 checkpoint — 2026-11-15

TASK-158 is pushed at `68731ae`. TASK-159 audits the complete platform evaluator
and has evidence for 49/77 Parity, 28 Partial: exact injected/live manifests,
sorting/scoring details, installed CLI discovery, and fail-closed process
errors. Initial audit findings were repaired and re-audit is clear. Focused 12
and full Python 2,630/7 pass. Commit/push, inspect CI, continue next Partial.

## TASK-160 checkpoint — 2026-11-15

Evaluator facade parity is locally complete after two repaired audit rounds.
Success-only seed caching, retry behavior, defaults, and explicit/injected
aliases pass Rust 7/Clippy, focused 19, and full Python 2,630/7. Inventory is
50/77 Parity and 27 Partial. Commit/push, inspect CI, continue next module.

## TASK-161 checkpoint — 2026-11-16

TASK-161 is locally complete on `release/agentrouter-v0.5-rc1`. The grading
facade matches Python in default/injected and classification/full modes,
classification precedes runtime discovery, deterministic full reports compare
exactly after removing only timing medians, malformed context fails closed, and
isolated process fixtures no longer inherit Cargo's CLI path. Independent
re-audit is clear. Rust workspace/strict Clippy, Ruff, 27 focused checks, and
full Python 2,642/7 pass. Inventory is 51/77 Parity and 26 Partial. Commit/push,
inspect Windows/macOS CI, then continue the next Partial evaluation module.

## TASK-162 checkpoint — 2026-11-16

Runner full-module parity is locally complete and independently clear. Rust owns
runtime discovery and bounded provenance; selection, filtering, failures, CLI
normalization, and complete scorecards match their Python contracts. Full Rust
workspace/Clippy, Ruff, 40 focused checks, and Python 2,660/7 pass. Inventory is
52/77 Parity and 25 Partial. Commit/push, inspect CI, continue the next Partial.

## TASK-165 checkpoint — 2026-11-16

TASK-162 is pushed at `79c70b0`; Rust migration CI, security, website, and
mutation pass, while Windows Python exposed two real path/open races. TASK-165
repairs both; independent review is clear and focused 46/Ruff/Clippy pass. Push
and require hosted Windows confirmation before considering this repair closed.

## TASK-164 checkpoint — 2026-11-16

Server request/response schemas are independently cleared for Parity. Rust now
exports every Python constant, including `MAX_TOOL_NAME_CHARS`; the differential
suite covers defaults, coercions, bounds, extra policy, owned and passthrough
responses, malformed/nullable risk and tools, arbitrary-precision integers, and
non-BMP exact/max+1 boundaries for every constrained string. Focused 93, API
Rust tests, workspace Rust tests/strict Clippy, and Ruff pass. Full Python
regression passes 2,696/7 in 346.49 seconds. Inventory: 53/77 Parity, 24 Partial.
Do not discard untracked TASK-163: its audit records that registry parity depends
on completing adapter-base and real adapter behavior.

## TASK-166 checkpoint — 2026-11-16

Annotation schema parity is independently clear after a P1 repair. Candidate,
AnnotatorLabel, ItemLabels, and AdjudicatedItem now validate inside public Rust
deserialization, including nested labels. Public constants, all required/default/
null and unknown-field cases, agreement edges, arbitrary integers, scalar
coercions, and expanded datetime boundaries compare directly. A newly exposed
positive half-microsecond mismatch was repaired. Direct 77, production-path 108,
evaluation Rust tests, strict Clippy, and Ruff pass. Full Rust workspace/Clippy
and Python 2,719/7 pass. Inventory: 54/77 Parity, 23 Partial.

## TASK-167 checkpoint — 2026-11-17

Server-service parity is independently clear. Rust now provides home and
no-argument registry facades, direct-call argument defaults, metadata-only active
OpenTelemetry spans, and correlated route logging without duplication. The
service differential covers list/classify/route/persistence/feedback/dry-run and
malformed/error paths. Focused 102, full Rust workspace/Clippy, and Ruff pass;
full Python regression passes 2,728/7. Inventory: 55/77 Parity, 22 Partial.

## TASK-203 checkpoint — 2026-11-17

The fail-closed Rust execution planner is now the shared preflight for the
guarded CLI execution path after persisted safety and recorded-route checks.
API/CLI adapter readiness is explicit; dry-run remains read-only and manual
routes remain operator handoffs. `cargo test --locked -p agentrouter-execution`
(5), workspace check, and formatting pass. Continue with separate adapter
hardening and orchestration runtime work; do not claim execution or production
readiness while the hosted context-band gate, human labels, live validation,
and deployment approvals remain open.

## TASK-204 checkpoint — 2026-11-17

Orchestration planning now rejects duplicate dependencies and empty side-effect
keys before scheduling. Five focused tests and strict crate Clippy pass. The
workflow crate remains execution-disabled; continue with owner-authorized
runtime lifecycle work only after adapter and release gates are addressed.

## TASK-205 checkpoint — 2026-11-17

Current optimized Rust-only smoke is green for init, route persistence, doctor,
and MCP negotiation. Planning correctly fails closed for an unavailable host by
default and only previews it with `--include-unavailable`; execution remains
disabled. Release build and cargo audit pass, with the known unmaintained
chrono warning and no available fixed upgrade.

## TASK-206 checkpoint — 2026-11-17

`agentrouter workflow plan` is now available as a planning-only CLI surface.
It accepts JSON workflows, enforces explicit step/cost/tool policy, and rejects
malformed dependency declarations. Process smoke and locked CLI checks pass;
dispatch and workspace mutation remain disabled.

## TASK-207 checkpoint — 2026-11-17

`WorkflowRuntime` now covers pending/running/succeeded/failed/cancelled state,
dependency unlocks, retry budgets, cancellation, and aggregated outputs/errors.
Seven focused tests and strict Clippy pass. Keep actual adapter lifecycle and
workspace mutation behind the owner-authorized execution milestone.

## TASK-208 checkpoint — 2026-11-17

The unified Rust CLI now exposes read-only `contract check` and `contract diff`
surface tooling. Baseline validation, additive compatibility, and breaking
surface exit behavior are covered by focused process tests. The command reports
that it is not a live-schema check; Python remains authoritative for that gate.

## TASK-209 checkpoint — 2026-11-17

The TypeScript parity helper now initializes Rust homes with the Rust `init_cli`
binary. The required Rust-backed live suite passes all 18 tests with zero skips;
it remains local evidence and does not clear external release gates.

