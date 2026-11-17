# Release Readiness

## Current checkpoint — 2026-11-18

Latest local verification on 2026-11-18 passes 2,738 Python tests with 7
expected environment skips, 89/89 focused Rust contract/unified-CLI tests,
the locked optimized Rust workspace build, strict Clippy, and cargo audit.

At pushed RC head `71408b2`, the macOS root-alias repair and TASK-175 Windows
diagnostics path-format repair passed the complete hosted Rust/Python matrix.
Local release checks are green, but the frozen context-band
gate, human evaluation, live OpenAI validation, and promotion/deployment inputs
remain unresolved.

The local continuation also includes TASK-210: Rust evaluation `status` and
`prepare` now support JSON output with explicit fixture/real availability and
`SKIPPED_EXTERNAL` blockers. This improves automation readiness; it does not
provide the missing verified external dataset loaders or clear the release
gate.

TASK-211 adds an explicitly opt-in bounded Hugging Face rows-API loader for
five evaluation adapters. Banking77 was exercised against the live public
endpoint and produced 3,079 normalized records; no fixture fallback occurred.
This does not clear the human holdout gate or make Docker/model/annotation
workflows production-ready.
The subsequent full Python regression rerun passes 2,740 tests with 5 skips;
the existing adapter metadata/error contract remains byte-compatible.

TASK-212 narrows the Rust SQLite path-redirect surface: ordinary database
opens use SQLite no-follow semantics and reject a symlinked leaf without
modifying its target. The capability-pinned Linux init path remains covered
after a parent swap, while complete handle-native SQLite initialization and
sidecar race closure remain unresolved. This is hardening evidence, not a
release waiver.

TASK-213 adds the missing legacy MCP initialization gate and verifies the modern
stateless path remains compatible. The safe five-tool surface and bounded stdio
transport remain green, but broader MCP lifecycle/transport parity is still
unresolved; this does not clear release readiness.

TASK-214 adds no-follow semantics to the Rust diagnostic database check and
verifies a symlinked target is not followed. This is security hardening only;
the remaining SQLite sidecar/handle limitation and external release gates stay
unresolved.

TASK-215 extends the no-follow boundary to diagnostic-bundle database reads.
This closes another local redirect surface but does not clear the remaining
SQLite sidecar limitation or external release gates.

TASK-216 adds the public Rust `contract export` workflow with source selection,
deterministic evidence, and fail-closed breaking-change refusal. The command
uses the committed Rust OpenAPI artifact by default; live schema generation and
complete compatibility classification remain unresolved. Release readiness is
unchanged.

TASK-217 hardens bundle `size_bytes` reporting with symlink metadata after the
no-follow SQLite read. This does not change the external release gates or the
remaining handle/sidecar limitation.

TASK-218 adds a bounded Rust `contract check --live URL` verification path. The
local smoke matched the committed OpenAPI baseline; this does not clear the
frozen evaluation gate, live provider credential requirement, or deployment
approval gates.

TASK-219 aligns the Rust exporter with the owner-reviewed acceptance workflow:
routine exports still refuse breaking changes, while
`--accept-breaking --reason TEXT` records exact findings without erasing prior
manifest history. Full Rust workspace tests, strict Clippy, optimized build,
audit, and the acceptance smoke pass; release readiness is unchanged.

TASK-220 removes the Rust evaluation and annotation CLIs' and diagnostics'
reliance on their
build-time checkout by adding explicit project-root override and
working-directory discovery. Relocated-fixture smokes plus the 21-test
evaluation, 5-test annotation, and 15-test diagnostics compatibility suites
pass; this does not provide the external datasets or clear release gates.

TASK-221 sets Rust diagnostic-bundle artifacts to private Unix mode `0600`
without weakening capability-bounded creation or redaction. This is local
hardening evidence; full bundle metadata parity and external release gates
remain unresolved.

TASK-183 confirms the optimized locked Rust workspace build and release binary
help/version smoke locally. `cargo audit --no-yanked` reports no vulnerability
advisories across 207 locked dependencies; one unmaintained `chrono` warning
(`RUSTSEC-2026-0543`, no fixed upgrade currently listed) remains documented.

**NOT release ready.** TASK-173 hardens bundle writes against parent and
final-component symlink/reparse redirection and preserves opt-in database
snapshot behavior. Bundle parity remains Partial for complete metadata and
Windows edge evidence; external release gates remain unresolved.

**NOT release ready.** TASK-177 aligns stable diagnostic-bundle version/runtime
metadata and preserves redaction. Full interpreter-specific metadata parity and
the external release gates remain unresolved.

**NOT release ready.** TASK-178 repairs evaluation CLI status reporting; the
remaining evaluation-loader and external release gates remain unresolved.

**NOT release ready.** TASK-179 aligns the Rust `prepare` exit contract with
Python: one unavailable dataset fails honestly, while `--all` completes its
blocker report successfully. Real dataset loading and the frozen evaluation
gate remain unresolved.

**NOT release ready.** TASK-180 aligns the context-band command's human-readable
confidence intervals and formatting with Python. This improves evidence parity
but does not provide real external datasets or clear the frozen evaluation gate.

**NOT release ready.** TASK-181 tightens Rust SDK connect/read/write and
aggregate timeout bounds. Native read/write error classification and the
remaining external release gates remain unresolved.

**NOT release ready.** TASK-182 aligns Rust reliability with Python for
truncated response bodies by consuming the body before recording success. The
broader reliability lifecycle and all external release gates remain unresolved.

**NOT release ready.** TASK-184 adds the native SDK's matching loopback
regression for truncated response bodies. It prevents partial payloads from
being parsed as API results; native read/write phase taxonomy and all external
release gates remain unresolved.

**NOT release ready.** TASK-185 fixes the Rust plugin doctor's symlink-root
diagnosis so linked host directories fail closed with an actionable blocked
finding. Plugin lifecycle parity and all external release gates remain
unresolved.

**NOT release ready.** TASK-186 verifies website lint, production build, and
zero production dependency vulnerabilities. Hosting publication/deployment
credentials and approval remain unresolved.

**NOT release ready.** TASK-187 verifies sdist/wheel creation and isolated
installed-wheel CLI smoke. PyPI trusted-publisher setup, release creation, and
deployment approval remain unresolved.

**NOT release ready.** TASK-188 re-runs the affected cross-language surfaces
with 77 isolated compatibility tests passing. The external evaluation,
credential, promotion, and deployment gates remain unresolved.

**NOT release ready.** TASK-189 verifies local CycloneDX SBOM generation. The
artifact is ready for the release workflow but no GitHub Release, provenance
attestation, PyPI publication, or deployment has been authorized.

**NOT release ready.** TASK-190 adds the Rust registry's concrete adapter
facade and fixture lifecycle coverage. Real HuggingFace loaders remain
explicitly external-only, so evaluation parity and the frozen release gate
remain unresolved.

**NOT release ready.** TASK-191 hardens MCP malformed-input behavior with
fail-closed request and argument tests. The MCP row remains Partial for full
transport/lifecycle parity and all external release gates remain unresolved.

**NOT release ready.** TASK-192's complete isolated Python regression is green
at 2,735 passed and 7 skipped. The frozen evaluation gate, human/live
validation, promotion, and deployment approvals remain unresolved.

**NOT release ready.** TASK-193's final optimized Rust build, version/help
smoke, and dependency audit are green. The frozen context-band gate, human
evaluation, live validation, PR review, promotion, publication, and deployment
remain unresolved.

**NOT release ready.** TASK-194 closes the callable-factory portion of the Rust
registry surface, but real external dataset loaders and the release gates
remain unresolved.

**NOT release ready.** TASK-195 confirms the optimized binary's fresh-home and
MCP smoke behavior. This is local evidence only; hosted promotion and external
release gates remain unresolved.

**NOT release ready.** TASK-196 confirms 17 adapter/base differential tests
pass. This does not provide Rust real-dataset loading or clear the frozen
evaluation and promotion gates.

**NOT release ready.** TASK-197/198 add planning-only execution and
orchestration crates with 8 focused unit tests and strict Clippy/format checks.
They intentionally keep remote execution, provider/CLI adapters, agent
dispatch, tool grants, and workspace mutation disabled. The remaining runtime
implementation and external release gates are unresolved.

**NOT release ready.** TASK-199 exposes the planning-only path as
`agentrouter plan` and verifies fresh-home CLI smoke. It still does not enable
provider/CLI adapters or multi-agent dispatch, and the external release gates
remain unresolved.

**NOT release ready.** TASK-200 records matched local Python/Rust routing
benchmarks with Rust faster across all tested fleets. The result is not a
production latency SLO and does not clear the frozen evaluation or deployment
gates.

**NOT release ready.** TASK-201 verifies Python-absent Rust-only init, route,
plan, doctor, and MCP smoke. It does not clear the frozen evaluation gate or
owner-controlled promotion, publication, and deployment requirements.

**NOT release ready.** TASK-202 adds a process-level CLI regression proving
that read-only planning stays disabled even when explicit policy flags are
passed. The external release gates remain unchanged.

**NOT release ready.** TASK-172 aligns the Rust doctor’s stable package,
server-extra, and contract summaries with Python and adds direct differential
evidence. Diagnostics remains Partial for runtime-specific and complete bundle
field parity; all external release gates remain unresolved.

**NOT release ready.** TASK-171 closes the provider refresh row after
independent review. Fixed HTTPS retrieval, bounded transport, key-only headers,
OpenRouter/OpenAI mapping, warnings/deprecations, dry-run, provenance, atomic
replacement, manual-registry preservation, and no-follow registry writes are
covered by Rust and process-level Python/Rust evidence. Full Rust workspace/
Clippy and Python 2,733/7 pass. Inventory: 59/77 Parity, 18 Partial. Frozen
evaluation, human/live validation, hosted promotion, main merge, tag, and
deployment gates remain unresolved.

**NOT release ready.** TASK-170 closes packaged annotation CLI parity after
independent review. Candidate and frozen-holdout resources are embedded with
checked-out-file precedence and deterministic fallback; exact hashes/counts and
the annotation CLI differential suite (88 checks) pass. Inventory: 58/77
Parity, 19 Partial. External evaluation, credential, hosted, and promotion
gates remain unresolved.

**NOT release ready.** TASK-176 closes the Python module entrypoint row with a
direct help/version differential; inventory is now 60/77 Parity and 17 Partial.
The remaining parity and external release gates are unresolved.

**NOT release ready.** TASK-169 closes the HTTP application lifecycle row after
independent review. The API executable uses the shared OS-aware home resolver,
and 114 focused HTTP/schema compatibility checks cover short-circuit request
IDs, auth/rate/CORS, registry error logging, and idempotency non-caching. Full
Rust workspace/Clippy and Python 2,731/7 pass. Inventory:
57/77 Parity, 20 Partial. External release gates remain unresolved.

**NOT release ready.** TASK-168 promotes observability after independent review:
task-local request IDs, compatible setter/scoped restoration, opt-in logging,
strict redaction, bounded API-error records, active OTel spans, and single-log
server error paths are covered. Nine focused tests, full Rust workspace/Clippy,
and Python 2,728/7 pass. Inventory: 56/77 Parity, 21 Partial. The frozen
context-band gate, human evaluation, live OpenAI validation, hosted checks,
main promotion, tag, and deployment remain unresolved.

## Previous checkpoint — 2026-11-16

**NOT release ready.** TASK-167 promotes the independently audited server-service
row. Home and registry facades, direct argument defaults, active metadata-only
OTel spans, correlated logging, and 102 focused checks pass with full Rust
validation. Inventory: 55/77 Parity, 22 Partial; full Python regression is still
running. Full Python regression passes 2,728/7.

**NOT release ready.** TASK-166 promotes the independently audited annotation
schema only after semantic validation became inseparable from public Rust
deserialization. Direct 77, annotation production-path 108, evaluation Rust,
strict Clippy, and Ruff checks pass. Inventory: 54/77 Parity, 23 Partial.
Full Rust workspace/Clippy and Python 2,719/7 pass.

**NOT release ready.** TASK-164 promotes the independently audited server-schema
row after complete constants, validation, serialization, passthrough, malformed,
nullable, and Unicode-boundary differential coverage. Focused 93, API Rust tests,
strict Clippy, and Ruff pass. Rust migration is 53/77 Parity with 24 Partial rows.
Full Python regression passes 2,696/7; external release gates remain unchanged.

**NOT release ready.** TASK-162 promotes the independently audited runner row.
Full Rust workspace/Clippy, Ruff, 40 focused checks, and Python 2,660/7 pass.
Rust migration is 52/77 Parity with 25 Partial rows. TASK-161 cross-platform Rust
CI passes; the frozen context gate and external release inputs remain blockers.

TASK-165 Windows path/open repairs are independently clear locally; hosted
Windows revalidation is pending and remains a release requirement.

**NOT release ready.** TASK-161 promotes only the independently audited grading
row: both grading modes, default/injected classifiers, discovery ordering,
platform detail, context evidence, and process failures are differentially
covered. Rust workspace, strict Clippy, Ruff, 27 focused checks, and full Python
regression pass (2,642/7). Rust migration is now 51/77 full-module parity with
26 Partial rows. Hosted cross-platform validation is pending. The frozen
context-band gate, human review/evaluation, live OpenAI validation, remaining
Rust modules, main promotion, tag, and deployment remain unresolved.

## Previous checkpoint — 2026-11-15

**NOT release ready.** At `5af3c55`, the hosted cross-platform Python and Rust
matrices, API, build, security, website, and critical mutation pass. PR #16 is
the sole open PR, has no GitHub review, and fails the unchanged frozen
context-band gate at 0.6667 < 0.90. Live OpenAI smoke skips without owner
credentials. Rust migration is 50/77 full-module parity with 27 Partial rows;
TASK-152 route observability passes local full Python/Rust regression: 2,590/5
Python tests at 92.052% statement, 87.756% branch, and 91.064% combined
coverage; Rust workspace, strict Clippy, wheel build, and clean-wheel smoke pass.
Hosted TASK-152 validation awaits the RC push. Main promotion, tag,
and production deployment remain blocked by the documented gates and owner
inputs.

## Previous checkpoint — 2026-11-14

**NOT release ready.** At last pushed code head `9a7dc7a`, Rust workspace checks
pass on Linux/Windows/macOS and Python/Rust compatibility passes on Linux/macOS;
Windows compatibility and most Python/platform jobs are still running. The PR
workflow's enforcing gate fails at frozen context-band accuracy 0.6667 versus
0.90; the push workflow skips it. TASK-149's nested redaction differential is
in hosted validation. TASK-150's large-integer response parity and full Python
regression pass locally and await hosted checks. PR #16 has no GitHub reviews.
Live smoke skips without an OpenAI credential.

TASK-140's Rust SDK wire-contract comparison passes all nine endpoints with
present, absent, and blank API keys. TASK-141 adds an injected transport and
timeout seam, all-nine-operation `httpx.MockTransport` comparisons, typed
transport categories, idempotent close, fail-closed fixture input validation,
and credential-safe URL/body diagnostics. The focused SDK/reliability selection
passes 52 Python tests and ten Rust SDK unit tests; full Rust workspace, strict
Clippy, formatting, Ruff, and the full Python suite pass locally. The latest
Python regression is 2,580 / 5; the committed TASK-150 coverage report measures
92.030% statement, 87.712% branch, and 91.038% combined coverage.
Current hosted cross-platform validation is still running; the latest completed
code-head run passes the Python Linux 3.10–3.13 matrix and Rust/Python
compatibility on all three platforms. TASK-144 locally aligns Python and Rust
OpenAI adapters for every non-2xx response; its offline differential cases and
68 focused Python tests pass.
TASK-145 adds three direct CLINC150 normalization comparisons; the Rust adapter
transformation matches Python, while external Hugging Face loading remains
Partial. TASK-147 bounds native TCP connection setup using the configured SDK
timeout while preserving the whole-request deadline. The SDK remains Partial
for the wider `ureq` timeout model and generic read/write behavior. PR
#16 remains the sole open PR. Rust
CLI/HTTP/MCP parity, provider execution, external dataset loaders, evaluation
runner, and R5–R13 remain incomplete. Human annotation, live OpenAI validation,
main promotion, and production credentials remain owner inputs. No paid request
or production deployment occurred.

## Historical v0.5 assessment

**Status: NOT release-ready.** Canonical v0.5 release-candidate assessment,
updated 2026-08-08 (iter26, after TASK-011/012/013/014/015/016 merged to
`release/agentrouter-v0.5-rc1`, RC @ `5847c22`).

The **only** remaining blocker is the frozen held-out context-band gate. It cannot
be closed by tuning — it needs the human-labelled dataset that TASK-011 tooling and
TASK-012 operations produce. The gate and its 0.90 threshold are unchanged.

## Current evidence

| Gate | State | Evidence |
|---|---|---|
| Offline routing and exact model/host output | Pass | Routing and CLI suites (RC) |
| High-risk execution and injection protections | Pass | Safety, execute, injection suites |
| Evaluation grade | Pass | ~98/100 canonical run; 6/7 gates pass |
| Six non-context evaluation gates | Pass | `artifacts/evaluation/result.json` |
| Frozen held-out context generalization | **Fail (by design)** | 0.6667 accuracy vs unchanged 0.90 threshold (shipped rules-active; TASK-009 proved the 24-case dev set is a ceiling) |
| Critical-module mutation thresholds | **Pass** | Linux mutmut 3.6.0, 923 mutants: overall 0.9837; safety_policy_execution 0.985 (>=0.95); routing_engine 0.9815 (>=0.85); no safety/policy/execution-bypass survivor |
| Safe reversible plugin lifecycle | Pass | Plugin suites green |
| Full local matrix | Pass | `pytest` 684 passed, 3 env-skips + 33 hook tests (2026-08-08; local env watchdog issue resolved) |
| Linux/Windows GitHub checks | Pass; enforce-release-gate correctly gated to promotion only | CI matrix 3.10-3.13 + test-windows + build-smoke + Security + release-readiness-report + Critical Mutation Testing green on RC @ `5847c22`; `enforce-release-gate`/`live-smoke` skip on task/RC pushes by design (TASK-014) |
| Dependency audit | Pass | `pip-audit -r requirements.txt`: no known vulnerabilities |
| Clean wheel install/lifecycle | Pass (re-verified 2026-08-08) | Wheel builds; installed into a fresh venv outside the repo; `providers status/doctor/rollback/restore` + `route` exercised, incl. corrupt-catalog exit 3 |
| Context-band dataset program | Delivered (labels pending) | TASK-011/012 merged; final human labels are the external TASK-012 step |
| Catalog trust + reversibility | Delivered | TASK-013 + TASK-015 merged: provenance block, atomic refresh, deprecation reporting, rollback/restore, `providers doctor`; security review 0 critical, all medium/low fixed |
| CI release-gate semantics | Delivered | TASK-014 merged; report (non-enforcing) vs enforce (promotion-only) split |

The 0.945 value previously used for context readiness came from the 165-case
in-sample gold set. The canonical generalization gate now uses the frozen,
checksum-locked 45-case holdout and is deliberately not tuned after its final run.

## External production prerequisites

Live provider verification, paid-model benchmarking, hosted deployment,
marketplace publication, beta feedback, and operational sign-off still require
credentials, budget, infrastructure, or owner decisions. These do not excuse the
three local/CI blockers above.

## TASK-153 recovery — 2026-11-15

Recovered strict bundle redaction in a persistent managed checkout based on c7d8180.
Python focused tests: 88 passed, 1 skipped; Rust CLI library 75/75 and observability
6/6; strict differential 1/1. Full Rust workspace, strict workspace Clippy, Ruff,
formatting, wheel/sdist and installed-wheel init/routing/bundle/API/MCP/plugin smoke
pass. Independent Python and Rust review found no blocking issue. Full Python
regression passes 2,597/7 in 501.42 seconds with 92.004% statement, 87.789%
branch, and 91.034% combined coverage. No thresholds or frozen data changed.
Bundle remains Partial for filesystem and JSON edge-case behavior. TASK-154 will
address reproduced Python artifact overwrite, then evaluation grading/platform
orchestration is next.

## TASK-154 exclusive artifact creation — 2026-11-15

Local release evidence passes: focused 95/1, full Python 2,604/7, 92.021%
statement and 87.833% branch coverage, independent review, hooks, Bandit,
wheel/sdist build, and installed-wheel exclusive-create smoke. Hosted
validation follows the RC push. Overall release readiness remains held by the
existing frozen evaluation and external requirements.

## TASK-155 fail-closed holdout grading — 2026-11-15

Malformed supplied holdout evidence can no longer be replaced by an easier
metric. Local differential, Rust workspace, Clippy, review, and full regression
evidence pass. Thresholds and frozen inputs are unchanged. Overall release
readiness remains held by the measured frozen gate and external requirements.

## TASK-156 consistent injected grading — 2026-11-15

The measured scorecard no longer mixes an injected classifier with the default
classifier. Local compatibility, Rust tests, review, and full regression pass.
The public runtime remains Partial; overall release readiness remains held by
the frozen gate and external requirements.
## TASK-157 public grading runtime — 2026-11-15

Default Rust grading now discovers packaged models and the installed CLI surface
and fails closed when either is unavailable. Independent review and full Python
2,613/7 pass. No release threshold or frozen data changed; readiness is held.
## TASK-158 evaluation CLI contracts — 2026-11-15

Rust evaluation CLI argument/error parity and TASK-157 cross-platform
formatting are repaired. Full Python 2,626/7 and independent review pass.
No release threshold or frozen data changed; readiness remains held.
## TASK-159 platform evaluator parity — 2026-11-15

The platform evaluator meets the full-module differential bar after rejected
evidence was repaired with real process failures and manifest consistency.
Inventory is 49/77 Parity; production readiness remains held.

## TASK-203 execution preflight — 2026-11-17

The guarded Rust CLI execution lifecycle now calls the fail-closed execution
planner after persisted safety and route-integrity checks. Planner readiness
flags distinguish API and CLI adapters; dry-run stays preview-only, and the
planner cannot execute. This improves release safety but does not satisfy the
remaining live credential, human-evaluation, hosted-gate, or deployment
requirements.

## TASK-204 orchestration input hardening — 2026-11-17

Malformed workflow dependency and side-effect declarations now fail closed
before planning. This is a safety improvement only; orchestration dispatch,
workspace mutation, cancellation, live adapters, and release gates remain
open.

## TASK-205 current release smoke — 2026-11-17

The current optimized binary passes isolated Rust-only init/route/doctor/MCP
smoke and release build/audit. Unavailable execution hosts fail closed by
default; explicit preview mode remains non-executing. This is validation
evidence, not production deployment or release promotion.

## TASK-206 workflow planning CLI — 2026-11-17

The unified CLI exposes bounded workflow planning with execution disabled.
This adds auditable orchestration planning but does not satisfy live adapter,
cancellation, deployment, or release-gate requirements.

## TASK-207 orchestration lifecycle state — 2026-11-17

Workflow lifecycle transitions, retry budgets, cancellation, and aggregation
are now testable without dispatch. This improves safety evidence but does not
constitute live execution, deployment, or release readiness.

## TASK-208 Rust contract CLI surface — 2026-11-17

The unified CLI now exposes read-only `contract check` and `contract diff`
commands over the committed OpenAPI baseline. This improves CLI surface
coverage but explicitly does not replace the Python live-schema gate; human
evaluation, live credentials, promotion, and deployment approvals remain
unresolved.

## TASK-209 TypeScript SDK live Rust parity — 2026-11-17

The TypeScript SDK's Rust live parity now initializes homes with the Rust
`init_cli` binary and passes all 18 loopback tests with zero skips. This closes
a local integration gap but does not clear the frozen evaluation, promotion,
or deployment gates.
