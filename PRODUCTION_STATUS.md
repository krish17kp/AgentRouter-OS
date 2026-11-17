# AgentRouter OS Production Completion

Updated: 2026-11-18

## Latest verification slice — TASK-270

The complete Rust/Python compatibility selection passes **738 tests with 1
expected skip** in 98.27 seconds. The only warning is the existing
non-failing Starlette/httpx deprecation. No compatibility regression was found;
the canonical release gate remains held independently.

## Latest continuation slice — TASK-268

Rust evaluation CLI numeric parsing now accepts negative integers like Python;
`--limit -1` produces the same empty deterministic sample. The focused Rust
evaluation CLI suite passes 25 tests. Release and deployment gates are
unchanged.

## Latest continuation slice — TASK-267

Rust evaluation CLI parsing now treats `--languages ""` as no filter, matching
Python. The focused evaluation CLI/runner selection passes 44 tests. Release
and deployment gates are unchanged.

## Latest continuation slice — TASK-266

The Rust registry facade now reports the committed `agentrouter-gold` benchmark
as `ready`, matching Python while keeping real mode explicitly external. The
evaluation crate passes 16 unit tests and the focused Python/Rust selection
passes 13 tests. Release and deployment gates are unchanged.

## Latest continuation slice — TASK-265

Rust real-mode MASSIVE collection now passes the requested language list into
the loader, fetching only the selected Hugging Face locale configs and keeping
Python's empty-list and unknown-language semantics. The focused Rust/Python
evaluation selection passes 58 tests; the workspace passes all tests, strict
Clippy, and formatting. This does not change the external-data, human-gate,
hosted-approval, or deployment state.

## Latest hosted-state slice — TASK-264

Live PR state confirms PR #16 is still mergeable but unstable: remote head
`71408b2` has green ordinary Python/Rust/API/security/website/mutation checks,
with `live-smoke` skipped and `enforce-release-gate` failing only on the frozen
context-band threshold. There are still no reviews or review requests. No
remote mutation occurred.

## Latest verification slice — TASK-263

The full Python suite now passes **2,782 tests with 7 expected skips** in
233.09 seconds. The only warning remains the non-failing Starlette/httpx
deprecation. This is a verification refresh after TASK-262; no release gate or
deployment state changed.

## Latest continuation slice — TASK-262

Evaluation `prepare --limit` now reports a deterministic smoke subset in both
Python and Rust. The adapter contract still validates the complete real source,
then applies the shared seed-0 sampler; the Python real-mode regression passes
8 cases and the locked Rust workspace plus formatting pass. No external data
was downloaded and no release gate changed.

## Previous continuation slice — TASK-257

The complete Rust/Python and Rust CLI compatibility selection after TASK-256
passes 893 tests with 1 expected skip. The existing Starlette/httpx warning is
non-failing; no compatibility regression was observed.

## Latest continuation slice — TASK-260

Release-readiness, quality, production-readiness, project-status, and known-
limitations documents now point to the current verification evidence while
preserving historical checkpoints. Runbook checks pass; no release gate or
deployment state changed.

## Latest continuation slice — TASK-261

Current release artifacts are validated: isolated PEP 517 wheel/sdist build,
Twine metadata checks, required wheel-asset inspection, website lint/build, and
Rust dependency audit all pass. The audit reports only the known unmaintained
`chrono` warning with no fixed upgrade; no vulnerability advisory was found.

## Previous continuation slice — TASK-258

The unified Rust top-level help now advertises the complete public prompt
generation syntax (`[TASK]`, `--from`, `--tool`, and `--out`), matching the
implemented leaf command. The focused help/version compatibility test and
format check pass; behavior and release gates are unchanged. The subsequent
full verification passes 2,781 Python tests with 7 expected skips, 893
Rust/Python compatibility tests with 1 expected skip, and the workspace-wide
Rust suite with strict Clippy.

## Previous continuation slice — TASK-259

Rust diagnostic-bundle JSON now uses Python-compatible ASCII escaping for
non-ASCII content, including surrogate pairs for emoji. The focused
diagnostics/bundle selection passes 45 tests, strict Clippy and formatting
pass, and bundle safety/redaction behavior is unchanged.

## Previous continuation slice — TASK-256

Unified Rust `hosts` and `models` inspection commands now preserve Python's
registry failure exit code (3) when the home is uninitialized, with four
process-level regressions. The focused selection passes 5 cases and strict
Clippy remains green.

## Previous continuation slice — TASK-255

Rust `doctor --bundle` now preserves Python's actionable
`Could not write the bundle:` error prefix while retaining exit code 2 for
unsafe or existing destinations. The diagnostics and bundle compatibility
selection passes 45 tests; the Rust CLI crate passes 89 tests with strict
Clippy and formatting.

## Previous continuation slice — TASK-254

Rust `doctor` human-readable output now matches Python's remedy indentation,
failure guidance, warning pluralization, and clear next-step wording. JSON
output remains unchanged. The focused diagnostics compatibility suite passes
18 tests and the Rust CLI crate passes 89 tests with strict Clippy and
formatting.

## Previous continuation slice — TASK-253

The unified Python and Rust doctors now agree on initialized registry counts.
Python diagnostics previously reported the loader tuple length (`2`) instead
of the eight loaded seed models; it now unpacks the loader result, with a
process-level differential covering the complete `registry.load` check.

The focused diagnostics compatibility suite passes 17 tests. TASK-252's OTel
reporting fix remains included; broader observability lifecycle and release
gates are unchanged.

## Previous continuation slice — TASK-252

Rust `doctor --json` now reports the actual OpenTelemetry opt-in state through
the shared observability crate. The focused diagnostics compatibility suite
passes 16 tests, while the Rust CLI crate remains green at 89 tests with strict
Clippy and formatting. This is a diagnostics parity increment only; it does
not claim full observability lifecycle or release readiness.

## Previous continuation slice — TASK-251

Rust unified command help now matches Python's successful `--help` behavior for
the leaf commands `init`, `explain`, `feedback`, `stats`, `prompt`, `doctor`,
and `dashboard`, in addition to the route and core subgroup help slices.
The combined route/unified compatibility selection passes 72 tests; the locked
Rust CLI crate, strict Clippy, formatting, and diff checks pass. This improves
R4 CLI parity but does not close the remaining full CLI, provider, evaluation,
human-gate, or deployment work.

TASK-247 adds Python-compatible text and structured JSON output to unified Rust
`explain`, with a process-level regression for both forms. The focused unified
selection is 36 tests and the Rust CLI crate remains green at 89 tests with
strict Clippy and formatting. This remains an R4 parity increment only.

TASK-248 adds named `--tool` forwarding and Python-compatible `--out PATH`
prompt generation through the unified command and direct decision probe. The
focused decision/unified selection is 42 tests; output files use no-follow
opening and reject hard-linked destinations.

TASK-249 adds unified task-based `prompt generate TASK`, using the existing Rust
classifier/routing/prompt pipeline and matching Python's output/newline
contract. The focused decision/unified selection is 43 tests; execution stays
disabled.

TASK-250 aligns task-prompt configuration semantics: Rust uses configured
weights but preserves Python's omission of the route policy cap in this
prompt-only path. The focused decision/unified selection is 44 tests.

TASK-251 aligns the public stored-prompt trailing newline with Python while
preserving the direct probe's historical output contract. The focused
decision/unified selection is 45 tests.

The complete Rust/Python and Rust CLI compatibility selection after TASK-251
passes 889 tests with 1 expected skip; the existing Starlette/httpx warning
remains non-failing.

The complete Rust/Python and Rust CLI compatibility selection after TASK-250
passes 888 tests with 1 expected skip; the existing Starlette/httpx warning
remains non-failing.

The complete Rust/Python and Rust CLI compatibility selection after TASK-249
passes 887 tests with 1 expected skip; the existing Starlette/httpx warning
remains non-failing.

The complete Rust/Python and Rust CLI compatibility selection after TASK-248
passes 886 tests with 1 expected skip; the existing Starlette/httpx warning
remains non-failing.

The complete Rust/Python and Rust CLI compatibility selection after TASK-247
passes 884 tests with 1 expected skip; the existing Starlette/httpx warning
remains non-failing.

## Definition of done

## Current continuation checkpoint — 2026-11-18

Current local verification on 2026-11-18 passes the full Python suite at
2,747 passed / 7 expected skips, the focused contract/unified-CLI differential
at 89/89, the optimized locked Rust workspace build, strict Clippy, and the
RustSec audit. The historical 2,740/5 figure below remains the earlier
TASK-211 evidence; the two additional skips are environment-dependent and do
not represent failures.

The fresh complete Rust/Python and Rust CLI compatibility selection after
TASK-246 passes 883 tests with 1 expected skip; the existing Starlette/httpx
deprecation warning remains non-failing.

TASK-242 rechecked the canonical gate after the route CLI slice: 165 cases,
98.23/100, and the sole failure remains context-band accuracy at 0.6667 versus
the unchanged 0.90 threshold. No holdout, threshold, or evaluation input was
changed.

TASK-243 also aligns direct route error handling: invalid options and missing
positionals now return a clean exit-2 `Error:` diagnostic, invalid registry or
configuration returns exit 3, and runtime storage failures return exit 1; all
emit no JSON on failure. The focused route suite (36 tests), Rust CLI tests,
strict Clippy, formatting, and diff checks remain green.

TASK-244 re-ran the complete Rust/Python and Rust CLI compatibility selection:
867 passed and 1 expected skip, with only the existing non-failing
Starlette/httpx deprecation warning.

The route parity slice also now covers successful direct and unified `route
--help` output; the focused direct route suite is 37 tests and the combined
route/unified selection is 58 tests.

TASK-245 adds successful Rust subgroup help for `models list`, `hosts doctor`,
and `providers status`; `registry list` and provider refresh/rollback/restore
help are now covered as well, and the combined route/unified compatibility
selection is now 65 tests.

TASK-246 adds successful help handling for the remaining existing leaf command
paths (`init`, `explain`, `feedback`, `stats`, `prompt`, `doctor`, and
`dashboard`). The combined route/unified compatibility selection is now 72
tests. The canonical gate remains unchanged and release readiness is still
false.

The local RC branch contains additional local commits after pushed head `71408b2`. TASK-208 adds
read-only Rust contract baseline/surface tooling, and TASK-209 makes the
Rust-backed TypeScript live suite independent of Python initialization. The
required SDK run is green at 18/18 with zero skips, and the Rust workspace,
strict Clippy, optimized build, and cargo audit remain green. This is not a
production deployment: the hosted frozen context-band gate is still
`0.6667 < 0.90`, human adjudication is open, live provider smoke has no
authorized credential, and hosting/domain credentials plus deployment approval
are still required.

TASK-210 adds structured JSON output to Rust evaluation `status` and `prepare`;
the focused compatibility suite is 20/20, and all eight external datasets are
reported honestly as blocked in this environment. This is automation-ready
evidence, not a real-loader or release-gate waiver.

TASK-211 adds a bounded, explicitly opt-in Hugging Face rows-API loader for
CLINC150, Banking77, MASSIVE, LongBench v2, and SWE-bench metadata. The live
public Banking77 endpoint was verified locally with 3,079 normalized records.
Offline defaults still report the opt-in blocker; no fixture is substituted.
After preserving the existing Python-facing metadata/error surface, the full
Python regression suite passes 2,740 tests with 5 documented skips.

TASK-212 hardens the Rust SQLite open with `SQLITE_OPEN_NOFOLLOW` for ordinary
database paths and adds a regression proving a symlinked database leaf cannot
redirect writes to an outside target. The Linux capability-pinned init path
continues to survive a parent-directory swap and create its database/WAL/SHM in
the pinned directory. Complete handle-native SQLite initialization and the
remaining sidecar leaf-swap race are still tracked as R4 limitations.

TASK-213 hardens Rust MCP legacy lifecycle handling: pre-initialize requests now
fail closed with JSON-RPC `-32002`, while modern discovery remains stateless.
Eight Rust MCP tests, strict Clippy, and the full Python/Rust MCP protocol
compatibility test pass. Non-stdio transport and broader MCP lifecycle parity
remain partial.

TASK-214 hardens `agentrouter doctor` so a symlinked decision database fails
closed instead of being inspected through an outside target. The focused
diagnostics regression passes; complete handle-native SQLite parity remains an
R4 limitation.

TASK-215 hardens Rust diagnostic-bundle data-shape collection with SQLite
no-follow semantics and a symlink regression. Normal bundle creation remains
green; complete handle-native SQLite parity remains an R4 limitation.

TASK-216 wires `agentrouter contract export` into the unified Rust CLI. The
command supports explicit source files, deterministic timestamps, JSON output,
and refuses detected breaking surface changes before replacement. Its default
source is the committed Rust OpenAPI artifact; live framework schema generation
and the full compatibility classifier remain Partial, so this does not clear
the release gate.

TASK-217 changes Rust bundle database size reporting to `symlink_metadata`, so
the post-open diagnostic read cannot follow a swapped database pathname. This
is additional local hardening; complete handle-native SQLite and sidecar race
closure remain R4 limitations.

TASK-218 adds Rust live OpenAPI verification through
`agentrouter contract check --live URL`. The transport is bounded and
redirect-free, validates local references, and reports the full Rust surface
compatibility result. A local HTTP smoke matched the committed baseline; live
framework generation and hosted release approval remain Python/owner-gated.

TASK-219 aligns Rust contract export with the documented acceptance workflow:
routine exports still refuse breaking changes, while
`--accept-breaking --reason TEXT` records the exact current findings without
erasing prior manifest history. Focused Rust contract tests, strict Clippy, and
a temporary CLI acceptance smoke pass.

TASK-220 makes the Rust evaluation and annotation CLIs plus diagnostics relocatable: they honor
`AGENTROUTER_PROJECT_ROOT`, discover repository ancestors from the working
directory, and only then fall back to the build-time manifest path. The
21-test evaluation, 5-test annotation, and 15-test diagnostics compatibility
suites plus strict crate Clippy pass; real external dataset availability
remains explicitly gated.

TASK-221 closes a Rust diagnostic-bundle privacy gap: Unix bundle artifacts are
now created with private `0600` permissions on the opened file handle. The
focused bundle tests, Python/Rust bundle checks, and strict Clippy pass; bundle
metadata/runtime parity remains Partial.

TASK-222 aligns Rust bundle `generated_at` with Python's six-digit UTC
ISO-8601 `+00:00` representation. The focused bundle and Python/Rust checks
remain green; broader bundle metadata/runtime parity remains Partial.

TASK-223 synchronizes the unified Rust CLI top-level help with the implemented
contract check/diff/export surface, including live and explicit-baseline checks
and owner-authorized breaking-change acceptance. The focused unified CLI help
check and formatting pass; release readiness is unchanged.

TASK-224 aligns Rust reliability transport classification for truncated HTTP
responses with HTTPX (`RemoteProtocolError`) while preserving timeout and
generic read-error distinctions. The focused differential, reliability crate
tests, strict Clippy, and formatting pass; broader reliability lifecycle parity
remains Partial.

TASK-225 aligns the native Rust SDK's truncated-response classification with
Python/httpx (`RemoteProtocolError`) while preserving timeout and generic
read-error categories. The focused native regression and 23-test SDK suites
pass; broader native lifecycle/transport parity remains Partial.

TASK-226 adds the explicit staging, canary, rollback, artifact/provenance, and
database-safety procedure in [`docs/DEPLOYMENT_PLAN.md`](docs/DEPLOYMENT_PLAN.md)
and links it from the release checklist/readiness report. It is a runbook only:
no staging or production deployment has occurred.

TASK-227 re-runs the authoritative local release gate from the current checkout:
165 cases, score 98.23, exit 1, and `release_ready: false`. Six gates pass; the
unchanged `context_band_accuracy>=0.90` gate remains at `0.6667`. The preserved
untracked historical task directory is the only local dirty-state source; no
evaluation or release inputs were modified.

TASK-228 rebuilds the current sdist and wheel with `uv build` and validates both
with `uvx twine check`; both artifacts pass. TASK-230 then modernizes the
license metadata, and the rebuilt artifacts no longer emit the prior
setuptools deprecation warnings.

TASK-229 installs the freshly built wheel into an isolated temporary
environment; the installed version, `init`, and local `route --json` smoke all
pass without a provider request or source-tree import dependency.

TASK-231 exercises the release workflow's CycloneDX command locally. The
generated 1.6 SBOM contains 59 components, including `agentrouter-os==0.5.0rc1`
with its declared MIT license. Release asset attachment and SLSA attestation
remain owner-controlled workflow actions.

TASK-233 adds the package-level `python -m agentrouter.reliability` entrypoint
for the soak profile. Its help surface and the focused Python/Rust reliability
compatibility suite pass; native transport phase taxonomy and broader lifecycle
parity remain partial.

TASK-234 rebuilt the current sdist and wheel after that entrypoint change. Both
pass `twine check` without metadata warnings, and an isolated wheel smoke
verified version, package-level help, initialization, and local routing.

TASK-235 re-ran the authoritative release gate after the package changes: 165
cases, score 98.23, exit 1, and `release_ready: false`. The sole failure
remains the unchanged context-band gate at `0.6667 < 0.90`.

TASK-236 re-ran the current Rust dependency audit and website checks. The audit
scanned 207 locked dependencies with no vulnerability advisories; website lint
and the Vite production build both pass. The existing unmaintained chrono
warning remains documented with no fixed upgrade available.

TASK-237 fixes a Rust evaluation CLI parity edge: `status` now reports fixture
availability from the registered path, matching Python even for empty fixtures.
The focused evaluation CLI suite (22 tests), Rust evaluation tests, Clippy,
formatting, and diff checks pass.

TASK-238 fixes the complementary `prepare` edge: an unknown dataset now reports
`UNAVAILABLE (adapter not importable)` and exits 1, matching Python instead of
surfacing a registry lookup error. The focused compatibility suite and Rust
evaluation tests remain green.

TASK-239 fixes Rust guarded execution exit semantics: missing child commands and
provider/host transport failures now return Python's runtime code 1 rather than
code 3. The unified CLI regression and Rust CLI crate checks pass.

TASK-240 aligns invalid Rust evaluation `validate-dataset` errors with Python's
`Invalid dataset:` prefix and exit code 3; the focused evaluation CLI suite now
passes 23 cases.

- [ ] PR review and hosted checks: PR #16 is the sole open PR against `main`, with no GitHub reviews or review requests. Pushed RC head `71408b2` is green across Rust Linux/Windows/macOS, Python/Rust compatibility on all three platforms, Python 3.10–3.13, Windows, macOS, Security, Website, and Critical Mutation. The enforcing release gate remains honestly held by frozen context-band accuracy `0.6667 < 0.90`; live smoke skips without credentials.
- [ ] Python-to-Rust migration covers every public Python module with contract parity; no shipped TODO or `unimplemented!()` remains.
- [ ] The full 77-module inventory is tracked in [`docs/RUST_PARITY_MATRIX.md`](docs/RUST_PARITY_MATRIX.md): 60 rows meet the full-module differential bar and 17 remain Partial. TASK-159–162 close platform, evaluator-facade, grading, and runner parity; TASK-164 closes server schemas; TASK-166 closes annotation schemas; TASK-167 closes server service; TASK-168 closes observability; TASK-169 closes the HTTP application lifecycle; TASK-170 closes packaged annotation CLI resources; TASK-171 closes provider refresh; TASK-176 closes the Python module entrypoint; broader migration differences remain.
- [x] Full Python suite: TASK-233's latest local Linux/Python 3.12 rerun passes 2,743 tests and skips 7 environment-dependent cases; the existing Starlette/httpx TestClient deprecation warning is non-failing. The TASK-152 coverage refresh measures 92.052% statement, 87.756% branch, and 91.064% combined; both required thresholds pass. Evidence is in [`docs/COVERAGE_REPORT_2026-11-15-TASK-152.md`](docs/COVERAGE_REPORT_2026-11-15-TASK-152.md).
- [x] Routing benchmark suite runs: 12/12 gold scenarios and 15 focused tests pass; dated results document records scope and limitations; the Rust release benchmark now runs the same 10/100/1,000 candidate fleets, with a paired local p50 ratio of 2.70×–3.25× under stated synthetic conditions.
- [x] Changelog, coverage evidence, and local latency measurements are committed to the release candidate. Candidate package version is now `0.5.0rc1`, with draft release notes in `docs/RELEASE_NOTES_v0.5.0rc1.md`; final `0.5.0` packaging and publication remain blocked on parity and all release gates.
- [ ] Release candidate promoted to `main` with a tagged release.

## Current recovery checkpoint

TASK-183 confirms the optimized locked Rust workspace build and release binary
help/version smoke. After adding the planning crates, the RustSec audit scans
207 locked dependencies with no
vulnerability advisories; one unmaintained `chrono` warning has no available
fixed upgrade and is recorded in
[`docs/RUST_DEPENDENCY_AUDIT_2026-11-17.md`](docs/RUST_DEPENDENCY_AUDIT_2026-11-17.md).

TASK-177 aligns stable diagnostic-bundle environment metadata. Rust bundles now
include the shared `agentrouter_version` alongside the Rust probe version and
explicit runtime marker, while preserving the existing secret-safe settings
allowlist. Focused bundle differential and Rust CLI tests cover the fields;
full runtime metadata parity remains Partial because Python and Rust report
different interpreter details.

TASK-178 repairs the Rust evaluation CLI `status` surface: it now reports the
actual real-dataset availability flag and suppresses blocker text when a real
loader is available, matching the Python command's contract. Evaluation CLI
focused compatibility (19 tests) and the full evaluation crate pass locally.

TASK-179 repairs the Rust evaluation CLI `prepare` exit contract. A single
unavailable dataset still exits 1 with an explicit `SKIPPED_EXTERNAL` blocker,
while `prepare --all` now exits 0 after reporting every unavailable source,
matching Python without falling back to fixtures. The evaluation crate passes
and the direct `--all` command reports all eight datasets honestly.

TASK-210 adds `status --json` and `prepare --json` records with explicit
fixture/real availability and blocker fields. Human-readable output and the
existing exit semantics remain unchanged; no external loader or fixture
substitution is claimed.

TASK-180 aligns the human-readable context-band evaluation report: Rust now
includes the bootstrap macro-F1 interval, renders intervals and per-band recall
with Python-compatible containers, leaves the checksum unquoted, and formats a
signed four-decimal accuracy delta. JSON output is unchanged; the evaluator
module remains Partial for real-data loading and runtime orchestration.

TASK-184 adds a real loopback SDK regression for truncated response bodies.
The native client returns `ReadError` instead of parsing a partial payload;
focused SDK checks, strict Clippy, formatting, and diff checks pass. Native
read/write phase taxonomy remains Partial.

TASK-185 fixes plugin doctor handling of a symlinked host root. Rust now emits
an actionable blocked-destination finding instead of an internal diagnostic
error, matching Python's fail-closed safety contract; focused regression and
local symlinked-root smoke pass.

TASK-186 verifies the website with clean lint, a successful TypeScript/Vite
production build, and zero production npm-audit vulnerabilities. The bundle is
local-only until the owner supplies hosting publication and deployment approval.

TASK-187 verifies Python sdist/wheel packaging and an isolated installed-wheel
smoke: version, `init`, and `route --json` all succeed. PyPI publication remains
blocked on the owner-controlled trusted-publisher setup.

TASK-188 re-runs the SDK, reliability, plugin, and diagnostics Python/Rust
compatibility suites in isolation: 77 tests pass in 26.33 seconds.

TASK-189 verifies the declared CycloneDX SBOM generation path: a valid 1.6
document with 46 components is produced outside the repository for the release
workflow. No release attachment or publication has occurred.

TASK-190 extends the Rust evaluation registry with a concrete adapter facade:
metadata, fixture/real availability, loading, preparation, sampling,
validation, checksum, and description are now represented and tested. Real
HuggingFace loading remains explicitly unavailable in Rust, so the base and
registry rows stay Partial and no external-data claim is made.

TASK-191 adds fail-closed MCP coverage for malformed JSON-RPC requests and
invalid tool arguments. The five safe read/route/explain tools remain the only
advertised surface; broader MCP lifecycle/transport parity remains Partial.

TASK-192 re-runs the complete isolated Python release suite: 2,735 passed,
7 skipped, and one existing Starlette/httpx deprecation warning in 449.37
seconds. No frozen evaluation data or release threshold changed.

TASK-193 re-runs the optimized locked Rust workspace build and dependency audit
after the final local slices. The release binary reports `0.5.0rc1`; the audit
finds no vulnerability advisories across 205 dependencies and repeats the
documented unmaintained-`chrono` warning with no fixed upgrade.

TASK-194 adds ordered lazy callable adapter factories to the Rust registry,
matching Python's `available_adapters()` construction surface for all eight
registered datasets. Real HuggingFace loading remains external-only.

TASK-195 exercises the optimized release binary from a fresh isolated home:
`init`, `route --json`, `doctor --json`, version, and MCP stdio negotiation all
pass. No credentials or deployment were used.

TASK-196 re-runs the adapter/base Python/Rust differential suite: 17 tests pass
across banking77, CLINC150, LongBench, MASSIVE, SWE-bench, and shared adapter
behavior. Real HuggingFace loading remains explicitly external-only.

TASK-197/198 add planning-only Rust boundaries for the previously missing
execution and multi-agent orchestration surfaces. Execution planning is
approval-gated, availability-aware, remote-disabled by default, and always
returns `execution_enabled: false`; orchestration planning validates bounded
DAGs, deterministic parallel groups, budgets, cycles, conflicting side
effects, tool allowlists, and idempotency keys while never dispatching or
mutating. Focused tests (4 + 4), strict
Clippy, and formatting pass. No execution adapter or orchestration runtime is
claimed.

TASK-199 wires those boundaries into the unified Rust CLI as read-only
`agentrouter plan`. A fresh-home init/route/save/plan smoke returns a planned
JSON record with `execution_enabled: false`; no host or provider is invoked.
Workspace check, strict Clippy, formatting, and focused planner tests pass.

TASK-200 re-runs the matched pure-routing benchmark: optimized Rust p50 is
26.86/260.33/2244.93 microseconds for 10/100/1,000 candidates versus Python
34.41/336.12/3560.56, with p95 lower at every fleet size. This is comparative
local CPU evidence only; it excludes I/O and provider execution.

TASK-201 verifies the optimized Rust runtime with Python environment variables
removed: isolated init, saved route, read-only plan, doctor JSON, and MCP
initialize all succeed. This proves the exercised surfaces do not require the
Python package at runtime; provider execution and deployment remain gated.

TASK-202 adds process-level regression coverage for `agentrouter plan`,
including explicit remote/approval flags that must not enable execution. The
focused unified CLI test passes 1/1.

TASK-175 repairs Windows diagnostics contract parity. Rust now renders the
contract directory through the native path formatter, matching Python's
platform-specific `Path` representation while retaining forward slashes on
POSIX. The hosted Windows failure is reproduced by the existing 14-test
diagnostics differential; the focused Rust CLI tests and Linux differential pass
with the repair. The next RC push must re-run the full Windows suite.

TASK-173 hardens Rust diagnostic bundle writes with no-follow parent creation, a
pinned capability directory, and exclusive creation for artifacts and opt-in
database snapshots. The storage
layer serializes the committed SQLite image, creates the destination exactly
once, and writes/syncs through the opened handle; artifact and snapshot
symlink/hard-link, directory-swap, and nested-parent escape regressions, Rust bundle/storage tests, strict Clippy,
and focused Python bundle/diagnostics checks pass. Bundle parity remains Partial
for full metadata and Windows-specific differential coverage.

TASK-172 aligns the Rust doctor’s stable package, server-extra, and contract
summaries with Python. The direct stable-check differential, diagnostics suite
(41 focused checks), Rust diagnostics tests, and strict Clippy pass. The row
remains Partial for runtime-specific and complete bundle field parity.

TASK-171 closes provider refresh parity after independent review. Generated
catalog writes now traverse the registry without following symlinks/reparse
points. Fixed HTTPS transport remains bounded and header-only; OpenRouter and
OpenAI mapping, warnings/deprecations, dry-run, provenance, atomic replacement,
manual-registry preservation, OpenAI key gating, and no-write failure behavior
have deterministic process-level Python/Rust evidence. The test-only fixture
seam is feature-gated and does not add a production URL override. Full Rust
workspace/strict Clippy (including the fixture feature) and Python 2,732/7 pass.
Inventory: 59 Parity / 18 Partial.

TASK-170 closes packaged annotation CLI parity after independent review. Rust
embeds the candidate pool and frozen holdout, prefers source-tree files for
development, and falls back to deterministic embedded bytes for installed
runtime use. Exact SHA-256/length/count assertions and source-independent pack
fallback tests pass; annotation CLI/schema compatibility passes 88. Inventory:
58 Parity / 19 Partial.

TASK-169 closes HTTP application lifecycle parity after independent review. The
Rust server executable now delegates default-home resolution to the shared
OS-aware service facade. Process-level coverage includes request-ID guarantees
on auth/rate/CORS short circuits, generic malformed-registry responses with
one redacted log, and non-cached validation idempotency errors. Focused
HTTP/schema compatibility passes 114 and full Rust workspace/Clippy pass;
full Python regression is running. Inventory: 57 Parity / 20 Partial.

TASK-168 closes observability parity after independent security review. Rust now
provides task-local request IDs plus a synchronous setter/scoped guard, opt-in
logging configuration, generic events, bounded strictly redacted API errors,
active OTel spans, and single-emission server error paths. Nine focused Rust
tests, full Rust workspace/Clippy, and full Python 2,728/7 pass. Inventory:
56 Parity / 21 Partial. HTTP error evidence is intentionally bounded and
message-only when no rendered traceback is available.

TASK-161 closes full grading-module parity. The public Rust default and injected
classifier paths match both Python grading modes, classifier-before-discovery
ordering, hidden platform-detail compatibility, context evidence validation, and
fail-closed installed-CLI failures. Independent review is clear. Rust workspace,
strict Clippy, 27 focused differentials, Ruff, and full Python regression pass
(2,642 passed, 7 skipped). Inventory: 51 Parity / 26 Partial.

TASK-162 closes evaluation-runner parity after three audit rounds. The Rust
runner owns selection, runtime discovery, bounded provenance, complete grading,
and fail-closed validation. Full Rust workspace/Clippy, 40 focused checks, Ruff,
and full Python regression pass (2,660/7). Inventory: 52 Parity / 25 Partial.

TASK-165 repairs the two hosted Windows failures without weakening assertions:
explicit evaluator executable discovery and non-following native exclusive
bundle creation. Independent review and focused 46/Ruff/Clippy pass; hosted
Windows revalidation is pending.

TASK-164 closes server-schema parity after independent audit. The differential
suite covers every public constant, request defaults/coercions/bounds, owned and
passthrough response shapes, unknown fields, arbitrary-precision integers, and
non-BMP Unicode boundaries for every constrained string. Focused 93, API Rust
tests, strict Clippy, and Ruff pass. Full Python regression passes 2,696/7 in
346.49 seconds. Inventory: 53 Parity / 24 Partial.

TASK-166 closes annotation-schema parity after independent audit exposed and
repaired a semantic-validation bypass in public Rust deserialization. Constants,
required/default/null behavior, nested unknown fields, agreement edges, scalar
coercion, arbitrary integers, and expanded datetime boundaries are covered.
Direct 77 and annotation production-path 108 checks pass; evaluation Rust tests,
strict Clippy, and Ruff pass. Inventory: 54 Parity / 23 Partial.
Full Rust workspace/Clippy and Python 2,719/7 pass.

TASK-153 is reconstructed in the persistent managed worktree after the temporary
checkout disappeared. Python focused tests pass 88/1; Rust CLI library 75/75,
observability 6/6, and strict Python/Rust differential 1/1 pass. Independent Python
and Rust reviews found no blocking issue. Wheel/sdist build and installed-wheel
init, routing, bundle privacy, API/MCP/plugin imports pass. Full Python regression
passes 2,597/7 with 92.004% statement and 87.789% branch coverage.
Bundle remains Partial for filesystem behavior and JSON edge-case parity. TASK-154
baseline reproduces overwriting an existing artifact in Python; Rust refuses it.

## Completed / in progress

- [ ] TASK-156 routes one injected Rust classifier through classification,
  routing, safety, and performance consistently. Default behavior remains intact.
  Scorecard/evaluation compatibility 42/42, Rust evaluation tests, strict Clippy,
  independent review, and full Python 2,610/7 pass. Grading/platform remain
  Partial pending TASK-157 default public runtime discovery.

- [ ] TASK-155 makes supplied context-band reports fail closed in Rust. Missing
  reports and explicit JSON null match Python None; numeric and boolean values
  match Python; malformed supplied structures return errors through every
  runner/probe. Focused 6/6, evaluation compatibility 40/40, full Rust workspace,
  strict Clippy, independent review, and full Python 2,609/7 pass.

- [ ] TASK-154 makes Python diagnostic artifact writes match Rust's exclusive
  final-path creation. Existing files, live/dangling symlinks, and injected
  file/symlink races are refused without changing existing content. Focused
  tests pass 95/1; independent review, hooks, Bandit, build, installed-wheel
  smoke, and full Python 2,604/7 at 92.021% statement and 87.833% branch
  coverage pass. Commit/push and hosted validation are next.

- [x] PR #33 reviewed and merged into RC `019233a`: Rust context-band feature extraction, validated artifact loading, stable softmax inference, and 15 prompt-level Python/Rust differential cases. All cross-platform CI checks passed; the learned model remains disabled in default routing.
- [ ] Rust doctor probe is locally validated on top of RC `07eb511`: stable JSON/text reports, safe checks for data, database, registry, generated catalogs, hosts, auth, runtime, and observability; an allowlisted redacted bundle with opt-in SQLite snapshot; environment values withheld; nine Rust CLI probe cases and focused Python compatibility tests pass. Its cross-platform CI passed on Linux, Windows, and macOS; promotion gate remains held by the frozen context-band evaluation. This is a partial R4 slice, not full CLI parity.
- [x] Rust quota-aware reranking is wired to `route_cli --verify-live`; eight Rust unit tests and ten Python/Rust differential cases cover unsupported/available/error preservation, verified exhaustion, no recommendation, invalid states, Python-compatible Unicode sanitation, and the CLI contract. PR #16's cross-platform CI passed for the RC base; production live adapters remain disabled.
- [x] Rust doctor quota checks share `agentrouter-hosts::detect_host`, provider mapping, and the bounded usage state machine; nine diagnostic compatibility tests pass. Full local regression passes; overall doctor parity remains partial.
- [x] `agentrouter/learning.py` now has a dedicated `agentrouter-learning` Rust crate; nine differential fixtures cover caps, sample thresholds, nullable ratings, exact explanations, and ties-to-even rounding. Route CLI learning-on/off parity remains covered.
- [x] Rust evaluation scorer/report/comparison slices passed the RC's cross-platform Rust and Python/Rust checks. The gold adapter is now full-module parity across metadata, availability, description, all 165 records, checksum, and deterministic sampling. Shared adapter base methods, external adapters, evaluation CLI/runner, and annotation remain Python-only.
- [x] TASK-148 expands the Rust API service differential across high-risk gates and explicit model preferences; the focused route-envelope selection passes 3 tests locally, and the full Python suite passes 2,572/5. Rust workspace, compatibility, and full Python checks pass on Linux/Windows/macOS at `7f29015`; the PR's frozen evaluation gate remains blocked. The service module remains Partial for logging/spans and full FastAPI lifecycle/middleware behavior.
- [x] TASK-149 adds exact Python/Rust differential coverage for nested JSON secret redaction. Its hosted Rust and Python/Rust checks pass on Linux/Windows/macOS at `9a7dc7a`.
- [x] TASK-150 removes a real Rust API response narrowing bug: `ModelSummary.context_window` now uses shared Pydantic integer coercion and preserves integers beyond `i64`. Large positive/negative integers, integer strings, booleans, and invalid inputs match Python. The hosted Python, Rust, security, mutation, and website checks pass at `5af3c55`; only the unchanged frozen evaluation gate fails.
- [x] TASK-151 refreshes routing research from LiteLLM, RouteLLM, RouterBench, and LLMRouterBench primary sources. Future candidates must beat best-single, cheapest, strongest, and random baselines on the same workload/pool and report quality, cost, latency, per-domain, and high-risk outcomes. Learned/cascade routing remains disabled pending consented labels and independent evaluation; no gate or frozen data changed.
- [ ] TASK-152 shares Rust observability between API and CLI, emits opt-in structured route records correlated through SHA-256 request-id digests, and strictly redacts credential-shaped values and keys at Python/Rust logging boundaries. Focused observability/correlation/HTTP compatibility pass 85/1; five Rust crate tests, full Rust workspace, strict Clippy, Ruff, wheel/sdist build, and clean-wheel smoke pass. Full Python regression passes 2,590/5 at 92.052% statement, 87.756% branch, and 91.064% combined coverage. Independent security review has no remaining release-blocking finding. Hosted checks await RC push. Spans, OTel, and complete API-error record parity remain Partial.

- [x] PR #22 MCP dependency bound merged to release candidate.
- [x] PR #25 staged Rust migration, registry and provider-status probes merged to release candidate as `99f5b76`; Python remains the shipping authority.
- [x] PR #20 `prepare --all` test made offline-safe; local focused tests pass.
- [x] PR #20 pytest constrained below 9 for compatibility with pinned `mutmut==3.6.0`; merged after current-RC CI and mutation checks passed.
- [x] PR #26 reviewed and closed as superseded; its legacy registry-print binary no longer compiled against the evolved registry API.
- [x] PR #27 website, #28 macOS CI, and #29 routing benchmark/coverage evidence merged to RC (`3fcfd05`). PR #21 was closed as redundant after confirming the RC already contains its hook interpreter change.
- [x] PR #13 plugin hardening merged into the release candidate at `9958dd8` after every check passed. The mutation campaign passed: 0.9693 overall, 0.9663 safety/policy/execution, 0.9815 routing, zero unreviewed survivors; portable coverage fixes also passed Linux, Windows, macOS and supported Python CI.
- [ ] PR #16 remains blocked by context-band accuracy 0.6667 < 0.90; no gate or label policy was changed.
- [x] macOS CI is merged for Python 3.12 and Rust workspace/parity; all checks on PR #28 passed.
- [ ] Rust R4 full CLI parity. TASK-089 now serializes race-safe SQLite initialization in both runtimes, but the new `doctor_cli` probe does not yet replace the shipped Python doctor and its bundle contract remains partial.
- [ ] Rust dashboard renderer/loopback server and Rust/Python feedback-stat parity merged via PR #30 at `bd98b6b`; the command remains a migration probe until the unified Rust CLI lands.
- [ ] Rust observability redaction/safe-echo helpers and bounded `ureq`/rustls OpenAI Responses transport merged via PR #30; structured logging, request context, traceback handling, and OTel integration remain unported. Live credentials, CLI wiring, and Python/Rust end-to-end parity remain open.
- [ ] Rust R5-R13 milestones and cross-platform parity. The bounded OpenAI Responses HTTPS transport is integrated into the guarded execution command with fail-closed policy checks; live credential smoke, complete lifecycle parity, and hosted validation remain outstanding.
- [x] PR #31 ported Rust `agentrouter-cli::harness` with eight Python/Rust cases, cross-platform CI, and dependency hardening; merged at `a246cf6`.
- [x] PR #33 ports Rust context-band model features, artifact validation, and inference; 15 prompts (30 feature/prediction checks) plus artifact-sync test passed locally and on cross-platform CI. It remains disconnected from the default rule classifier until evaluation approves enabling learned routing.
- [x] Rust AgentRouter gold adapter matches Python metadata, availability, description, loading, checksums, and deterministic sampling; exact JSON parity covers all 165 committed cases and a Unicode/defaults fixture. Cross-platform differential CI is added in this increment.
- [x] Shared Rust fixture adapter-base methods match six external adapter fixtures for metadata, availability, describe, loading/validation, checksums, deterministic sampling, and skipped-external real mode. External downloads and dataset-specific real-data transformations remain unported.
- [x] TASK-029 ports TwinRouterBench dynamic-track skip status; its Rust and Python/Rust checks pass on Linux, Windows, and macOS.
- [x] TASK-030 completes evaluation provenance parity with a Rust environment snapshot; its cross-platform Rust and Python/Rust checks pass.
- [ ] TASK-031 completes Rust evaluation schema parity for defaults, serialization, hash/checksum methods, and invalid-input validation. Local checks pass; hosted platform compatibility is finishing.
- [x] TASK-032 ports human annotation resolution and adjudication to Rust. Seven differential cases cover agreement, abstention, unresolved conflicts, and explicit human decisions; the required independent annotator round is still under **Needs Krish**.
- [x] TASK-033 ports Python-compatible prompt normalization, near-duplicate similarity, clustering, and leakage reports. Rust/Python checks pass across Linux/Windows/macOS; Ruff formatting is corrected. The frozen holdout remains read-only.
- [x] TASK-034 ports deterministic annotation splits, cluster preservation, and fail-closed frozen-holdout leakage checks. Local and cross-platform Rust/Python tests pass.
- [ ] TASK-035 ports annotation schemas with Python-compatible datetime normalization. Fourteen focused differentials and the Rust workspace, Clippy, format, Ruff checks pass. Scalar coercion and the full `fromisoformat` edge grammar remain incomplete, so the module stays Partial; hosted Rust/Python compatibility passes all three platforms.
- [x] TASK-036 ports the optional repository-impact graph signal. TASK-041/042/043 now match Python malformed-shape behavior, its four-entry LRU cache (including cached fallbacks and eviction), and contextual Unicode lowercase. Thirteen focused differentials, full Python regression, full workspace/Clippy/format/Ruff pass locally; cross-platform CI is pending push.
- [x] TASK-037 completes Rust annotation pack behavior: CPython-seeded shuffle for arbitrary integer seeds, resume filtering, label-free progress, order-preserving merge, disagreement-only adjudication packs, and Python-compatible CSV. Eight focused cases and the full local regression pass; cross-platform hosted checks pass on `dca1300`.
- [x] TASK-038 ports annotation candidate/dataset YAML, labels JSONL, sorted manifest JSON, and canonical split SHA-256. Four focused file/hash differential tests and the full Python regression pass locally, including exact JSONL/manifest bytes and Unicode hash parity. Windows CI exposed Python CRLF translation parity; fixed in `1c88b3c`; Rust workspace and Python/Rust compatibility now pass Linux, Windows, and macOS.
- [x] TASK-039 ports deterministic annotation candidate generation from the 63-prompt bank. Fifty generation differentials plus an exact bank-inventory case cover 5 positive/negative/arbitrary-width seeds, 10 Python slice counts, exact IDs/source/templates, and prompt ordering. Full Python regression is 1,868/6; Rust workspace, Clippy, format, Ruff pass locally. Linux/Windows/macOS compatibility passes on the newline-fix recheck.
- [x] TASK-040 ports `annotation.compare`: rules/learned/hybrid reports, macro-F1, per-band recall, Python-compatible seeded bootstrap CI, ECE, abstentions, and fallback rates. Five differential cases cover exact output and threshold behavior; full Python regression is 1,868/6, and full Rust workspace/Clippy/format/Ruff pass. Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `8a4286a`. The implementation does not alter the frozen release gate.
- [x] TASK-041 aligns the graph signal's valid-JSON malformed-shape behavior with Python, including Python iterable mappings/strings and raised errors for truthy scalar collections. Eleven focused graph differentials and full Python 1,875/6 passed locally; Rust workspace and compatibility checks pass Linux/Windows/macOS at `75d4690`. The cache semantics followed in TASK-042.
- [x] TASK-042 ports the graph signal's maxsize-four LRU cache, including cached unreadable/missing/invalid-JSON fallbacks and least-recently-used eviction. Twelve focused graph differentials and full Python 1,876/6 pass; hosted workspace/compatibility checks pass Linux/Windows/macOS at `7399b3b`.
- [x] TASK-043 matches Python's context-sensitive Greek final-sigma lowercase behavior in graph node/edge identifiers. Thirteen focused graph differentials, full Python 1,877/6, full Rust workspace/Clippy/format/Ruff pass locally; cross-platform CI follows push.
- [x] TASK-044 ports the complete frozen context-band evaluator: checksummed YAML loading, category validation, Python-compatible Unicode normalization and SequenceMatcher leakage checks, scoring, Wilson intervals, CPython-seeded bootstrap, historical comparator, and the frozen generalization report. Three Python/Rust differential tests compare the full release report, custom predictions/score output, sequence ratios (including autojunk behavior), and leak order; focused tests and evaluation-crate Clippy pass locally. The frozen score and release threshold were not changed.
- [x] TASK-045 ports the `agentrouter.evaluation` package facade as a Rust public module that re-exports the same three schema types; a Python/Rust contract test compares the public export list exactly.
- [x] TASK-046 ports the `agentrouter.annotation` package constants through a Rust facade; the cross-language test compares schema version, category order, and split names.
- [ ] TASK-047 adds the evaluator package facade, validated embedded seed-model loading, and the same seven exports. The seed catalog and export list have an exact local compatibility test; evaluator runtime orchestration remains partial because the underlying Rust evaluator ports still accept explicit catalogs/commands rather than discovering Python runtime state.
- [x] TASK-142 strengthens the evaluator facade differential to compare every normalized field of every embedded seed `ModelEntry` and checks Rust exports against Python's actual `__all__`. The focused compatibility test passes. The module remains Partial because Rust evaluator functions still lack Python runtime-state discovery and orchestration.
- [x] TASK-143 makes `agentrouter-evaluate run --all` query the sibling Rust CLI's command/group manifest instead of scoring the placeholder `evaluate`/`eval` pair. Missing sibling metadata fails closed. The end-to-end scorecard reports the actual CLI surface and passes focused cross-language verification; other evaluator API/runtime gaps remain Partial.
- [x] TASK-144 makes both OpenAI adapters reject every non-2xx status from an injected or native transport. Offline Python/Rust differentials cover 300, 302, and 399; the full OpenAI adapter selection passes 68 tests without live credentials.
- [x] TASK-145 adds direct full-output CLINC150 real-row normalization differentials for every ordered intent hint, unknown intents, `oos`, Unicode, source IDs, and duplicate semantics. Three focused cases pass. The adapter module remains Partial for the Python-only external dataset loader.
- [ ] TASK-146 adds HTTP status boundaries and rejects missing/malformed response statuses. Latest hosted mutation found one survivor caused by removing the missing-status fallback; the new regression fails closed and locally kills that exact mutant. Hosted full mutation revalidation awaits the next push.
- [x] TASK-048 ports the top-level package version accessor by reading the canonical `pyproject.toml` metadata at Rust compile time; exact Python/Rust version parity is tested.
- [ ] TASK-049 aligns annotation confidence deserialization with Pydantic's number, numeric-string, and boolean coercions. The schema compatibility suite now includes these inputs and passes 18 focused cases; annotation schema stays Partial pending complete datetime grammar and remaining scalar coercions.
- [ ] TASK-050 aligns Pydantic boolean coercion (booleans, 0/1 numeric forms, and recognized strings) and integer coercion for manifest schema versions; annotation schema remains Partial for remaining coercion surfaces.
- [x] TASK-051 confirms the evaluation-adapters and server package initializers intentionally expose no runtime symbols; Rust package markers and a differential export test now document that no-op public contract.
- [x] TASK-052 aligns manifest integer coercion for JSON numbers, booleans, signed/underscore integer strings, and integral decimal strings; differential tests also reject fractional, exponent, and malformed underscore strings as Python does. The `i64` representation still cannot match Python's unbounded integers, so annotation schema remains Partial.
- [x] TASK-053 adds Rust registered dataset specs and fixture collection, with differential coverage for ordering, profiles, every fixture, deterministic sampling, availability/checksums, Massive language filtering, real-mode blockers, unknown lookups, and error text. Remote dataset loaders and real-data adapter transforms remain Partial.
- [x] TASK-054 adds an offline Rust runner for registered profiles and datasets, classification grading, dataset quality, explicit provenance, and `measure_all` across all seven dimensions. Thirteen Python/Rust differential cases cover collection reports, end-to-end profile results, multilingual filtering, all scorecard dimensions, release gates, and fail-closed real-mode behavior. Automatic runtime environment, CLI-state discovery, and real dataset downloads remain Partial.
- [x] TASK-055 tightens annotation timestamp parity: focused cases cover Python-compatible date-only, compact offset, fractional seconds, comma fractions, omitted seconds, and rejected invalid separators/date shapes. TASK-057 adds the Python-compatible underscore separator across omitted seconds, fractional seconds, and timezone offsets (33 annotation-schema tests pass). The module remains Partial pending the remaining scalar coercion and full datetime grammar audit.
- [x] TASK-058 verifies the annotation schema's Pydantic integer-string coercion for integral decimals and underscore-separated digits, and rejects fractional/exponent/malformed forms. Its original signed-64-bit representation limit is addressed by TASK-111; the schema remains Partial for datetime grammar and other coercions.
- [x] TASK-059 closes additional datetime mismatches found by differential checks: reject leap seconds, accept Python-compatible signed numeric timestamp strings while rejecting integer exponent forms, and round timestamp microseconds like Python. The focused schema suite passes 49 cases; an additional 40-value timestamp corpus has zero Python/Rust mismatches.
- [x] TASK-060 adds Rust fixed-window rate limiting, bounded TTL idempotency caching, and per-key single-flight computation. Seven Rust unit tests and four Python/Rust differential tests pass, including environment configuration and capacity bounds. The HTTP middleware and full Python server lifecycle remain unported, so server limits stay Partial.
- [x] TASK-061 adds Rust catalog provenance reads, fetched-at/tool-version status fields, and sorted report-only deprecations.
- [x] TASK-062 extends Rust catalog operations with summaries, generated-catalog listing, rollback, and restore. Eight Python/Rust compatibility tests, nine focused Rust tests, and the expanded full Python suite pass; workspace tests, Clippy, Ruff, and formatting pass locally. Linux/macOS/Windows CI passes on `998efa2`; typed Python `CatalogError` and remaining error-shape parity keep the module Partial.
- [x] TASK-063 adds the Rust local-service SDK client for all Python SDK endpoints, with typed request options, optional API-key auth, null-field cleanup, structured HTTP errors and redirects disabled. Three local HTTP fixture tests and Linux/macOS/Windows Rust/Python CI pass; complete client/server end-to-end parity remains open because the Rust server is not yet ported.
- [x] TASK-064 makes Rust classification deserialization reject unknown fields like Pydantic and adds a direct JSON round-trip/rejection probe; the Python/Rust schema differential test passes. Unbounded Python integer and scalar coercion parity remain open, so `schema.py` stays Partial.
- [x] TASK-065 adds Rust classify, route, feedback and dry-run HTTP request schemas with field-bound validation. Three Rust tests, 13 Python/Rust compatibility cases, the full Python regression, Rust workspace tests, and workspace Clippy pass locally; field coercion, response passthrough types, HTTP middleware and the server lifecycle remain open, so `server/schemas.py` stays Partial.
- [x] TASK-066 adds typed and passthrough Rust HTTP response models and Pydantic-compatible boolean/integer coercion for supported ranges. The focused Python/Rust schema suite passes 35 cases; the full Python suite, Rust workspace tests, and Clippy pass locally. Python unbounded integers, HTTP middleware, and server lifecycle remain open, so `server/schemas.py` stays Partial.
- [x] TASK-067 ports `server/service.py` business functions into `agentrouter-api::service`: model/host listing, classification, no-log and persisted routing, decision lookup, feedback, and dry-run preview. It uses routing/storage/host crates directly. Forty-three focused Python/Rust differentials and the Linux/Windows/macOS hosted Rust/Python matrix pass on pushed head `218ef42`.
- [x] TASK-068 adds the Axum HTTP process and endpoints, graceful shutdown, request IDs, API-key checking, explicit-origin CORS, rate limiting, body bounds, and idempotent replay through shared `agentrouter-limits` primitives. The server and CLI share bounded rate/cache code, including a 16 MiB aggregate cache cap. Five live HTTP process tests, the focused Python/Rust and server checks, eight shared-limit Rust unit tests, all Rust workspace tests, strict Clippy, `cargo audit`, the Python regression, Rust 1.89 tests, and an optimized release build pass locally. Hosted Rust workspace checks pass on all three operating systems; the `b6d812c` Windows compatibility run exposed the OpenAPI Unicode issue addressed by TASK-069. Python remains the release authority.
- [x] TASK-069 matches FastAPI field-level 422 validation messages for 21 invalid request payloads, malformed JSON, and an unknown route; its cross-language HTTP tests compare full error responses. The OpenAPI contract stores the em dash as a JSON escape, preserving the same parsed schema while avoiding the Windows response mismatch. The full Python suite passes with 2,008 passed and 4 skipped; Rust workspace tests, strict Clippy, Rust 1.89 tests, release build, and focused HTTP parity tests pass locally. Linux/macOS hosted HTTP checks pass on `b6d812c`; hosted confirmation of these follow-up fixes is pending.
- [x] TASK-070 runs all 18 TypeScript SDK tests against both the Python server and the Rust HTTP process; all operations in the SDK capability manifest, validation errors, 404 handling, and request IDs are covered. TypeScript typecheck and both live test modes pass locally. The Rust CI workflow now installs Node 22 and runs the TypeScript suite on Linux, Windows, and macOS; hosted confirmation awaits the next push.
- [x] TASK-071 adds Python SDK round-trip and authentication checks against the Rust HTTP server, including no-log routing, persisted decisions, feedback, dry-run, and typed errors. The full Python suite passes; the parity harness passes Bandit after replacing its URL opener with a loopback socket probe and documenting its fixed executable/argument list. Hosted checks are pending.
- [x] TASK-072 adds `agentrouter-mcp`, a bounded stdio JSON-RPC server implementing the five Python MCP tools. The official MCP client confirms protocol negotiation, capabilities, tool schemas, structured results, and safe unknown-tool errors; the 4 MiB input-frame bound has a resynchronization test. The full Python suite, full Rust workspace tests, strict Clippy, formatting, and local protocol parity pass. Hosted checks are pending. The Python CLI remains supported; unified Rust CLI wiring is open.
- [x] TASK-073 adds offline OpenRouter/OpenAI model conversion and payload filtering in `agentrouter-registry::refresh`. Twenty-one Python/Rust differentials compare complete generated model records, all current OpenAI families, tier thresholds, filtering, and warning behavior. Full Python suite, Rust workspace tests, strict Clippy, formatting, and focused parity pass locally. Network retrieval, key handling, atomic registry writes, provenance, deprecation reporting, and CLI wiring remain Python-owned; hosted checks are pending.
- [x] TASK-074 adds Rust load and soak result models and a concurrent HTTP runner. Five Python/Rust compatibility checks cover summaries, a live loopback run, unique request IDs, redirect refusal, and soak resource samples. The full Python suite, full Rust workspace tests, strict Clippy, formatting, Ruff, and Bandit pass locally. Rust server lifecycle and complete transport-error parity remain open; cross-platform hosted checks are pending.
- [x] TASK-075 ports the historical classifier and routing-gold evaluator, score summaries, Markdown/CSV artifacts, and `legacy-gold`/`routing-gold` Rust CLI commands. Four Python/Rust tests compare all classifier and routing fixtures, artifact output, and the CLI. Remaining typed `GoldError` and JSON escaping differences keep the Python module Partial. Hosted Rust/Python compatibility, workspace, Python-version, site, and security checks pass on the pushed evaluator increment; the frozen release gate correctly remains failed.
- [x] TASK-076 adds Rust `agentrouter-evaluate dataset` commands for candidate generation, blinded packs, resumable human annotation, label-free progress, CSV export, disagreement-only adjudication, leakage-checked dataset builds, dev comparison, and frozen-prompt leakage reports. Four end-to-end differential tests cover all command paths, explicit adjudication, refusal of unresolved conflicts, and human-input resume. The annotation CLI stays Partial until full entrypoint/schema parity; Linux/macOS/Windows hosted compatibility, workspace, MSRV, Python, and security checks pass. The unchanged frozen release gate remains failed.
- [x] TASK-077 adds the unified Rust `agentrouter` executable and connects `init`, `route`, `explain`, `feedback`, `prompt`, `registry list`, provider status, hosts, models, doctor, dashboard, and dataset commands. The dataset flow is linked directly; sibling Rust tools handle existing binary-backed commands. Four end-to-end tests cover help/version, init/route dispatch, feedback persistence, host/model commands, dataset access, and honest rejection of still-unported commands. Local full Python and Rust suites, strict Clippy, formatting, Ruff, and Bandit pass; cross-platform hosted confirmation is pending. The CLI and `__main__.py` remain Partial because provider refresh, plugins, contract tools, execution, and several other Python commands are not ported.
- [x] TASK-078 connects Rust `stats` and provider catalog doctor/rollback/restore commands to the unified CLI. Five differential CLI tests cover JSON/text statistics, reversible catalog changes, healthy generated-catalog reporting, and corrupt-catalog failure. Local Rust workspace tests, strict Clippy, format, Ruff, Bandit, and the 2,044-test Python suite pass. Provider refresh, plugins, contract tools, execution, and other commands remain migration gaps; hosted confirmation follows push.
- [x] TASK-079 adds fixed-endpoint OpenRouter/OpenAI HTTPS retrieval to Rust refresh, with 20-second connect/read/write timeouts, redirect refusal, a 16 MiB response limit, header-only API keys, report-only deprecations, and atomic generated-file replacement. Four Rust transport/write tests and one unified CLI preflight test cover bounded behavior and missing credentials; the existing conversion differential suite remains green. The full Python suite passes with 2,045 tests and 5 skips at 91.38% combined coverage. OpenAI live catalog visibility still requires a user key; full refresh error/output parity remains Partial.
- [x] TASK-080 embeds the Rust HTTP and MCP service entrypoints in the unified CLI, preserving host/port defaults, the selected data home, inherited API-key settings, and MCP stdio. Nine focused checks cover validation, HTTP health/startup and shutdown, and MCP protocol negotiation/tool discovery. The 2,048-test Python suite, full Rust workspace tests, strict Clippy, formatting, Ruff, and configured Bandit pass locally; hosted confirmation follows push.
- [x] TASK-081 adds Rust `agentrouter execute` with stored-classification gate recomputation, provider opt-in, explicit confirmation, dry-run behavior, shell-free argv execution, host readiness and route-change checks, and a bounded no-retry OpenAI Responses request. Rust integration checks prove that high-risk and gate-tampered decisions never run; Python tests also pin the dry-run contract. The 2,051-test suite, full Rust workspace tests, strict Clippy, formatting, Ruff, and configured Bandit pass locally. Hosted confirmation and OpenAI live validation remain open.
- [x] TASK-082 adds 20 offline Python/Rust OpenAI adapter differential cases for request construction, credential privacy, bounded limits, validation errors, provider failures, refusals, malformed responses, and oversized bodies. Python now refuses redirects like Rust, verified against a loopback 302 endpoint. A direct legacy-provider dry-run test kills the three reported execution mutants. The hosted mutation campaign then found two mutants that removed the network timeout; the added delayed-endpoint check kills both locally. OpenAI adapter contract parity is covered; hosted confirmation of the final timeout checks is pending.
- [x] TASK-083 adds direct Python/Rust `check_usage` comparisons for no-live and unsupported states, all registered status states, invalid-state fail-closed behavior, and Unicode/control-character sanitization. The Rust status probe is fixture-only and makes no network calls. At that increment, adapter exception names still differed; TASK-085 closes that specific gap. The 2,081-test full Python suite passes with the adapter timeout regression included; the usage crate tests and full-workspace strict Clippy pass.
- [x] TASK-084 completes generated-catalog operation parity: typed Rust errors expose Python-compatible exception categories, and Python now uses no-follow byte reads plus exclusive no-clobber restoration. Differential cases cover malformed YAML/UTF-8, provider errors, restore collisions, Python-compatible date/sanitization behavior, missing/non-directory listings, backup history, and linked-file refusal. The full Python suite passes with 2,094 passed and 5 skipped; coverage is 92.52% line, 87.65% branch, and 91.42% combined. All Rust workspace tests, strict workspace Clippy, 57 focused catalog tests, Ruff, Bandit, and formatting pass locally. Linux/macOS hosted checks pass on `d5706b8`; Windows jobs are pending.
- [x] TASK-085 aligns Rust quota adapter failures with Python `check_usage` exception-name reporting through a typed `LiveCheckError`. Offline differentials cover `TimeoutError`, `ConnectionError`, and `ValueError` while confirming provider messages stay private. Nine usage crate tests, 35 focused Python/compatibility tests, and the full workspace pass; strict Clippy and formatting pass. The full Python suite passes with 2,097 passed and 5 skipped at 92.52% line, 87.65% branch, and 91.42% combined coverage. Hosted confirmation is pending push.
- [x] TASK-086 adds exact dashboard HTML differentials for empty/filled views, escaping, and truncation, and compares the live Rust server output against Python's real SQLite aggregates. Four focused dashboard checks and the full Python regression pass; Rust workspace tests, strict Clippy, formatting, and Ruff pass locally.
- [x] TASK-087 makes Python and Rust doctor database checks read-only, with matching safe error categories and remedies for empty and corrupt databases. Thirty-eight focused diagnostic and Rust compatibility tests pass, along with 27 Rust CLI tests and strict Clippy. The full Python regression passes with 2,103 tests, 5 skips, and 91.41% combined coverage.
- [x] TASK-088 bounds Python idempotency response retention to the same 16 MiB body budget as Rust. Thirty-seven focused Python/Rust compatibility and HTTP middleware tests plus all eight Rust limits crate tests pass; its full Python regression passed with 2,104 tests and 91.39% combined coverage.
- [x] TASK-089 serializes Python and Rust first-use SQLite schema creation/migration with an immediate transaction and in-lock schema rechecks. Sixteen simultaneous legacy-database connections pass in each runtime; focused cache mutations kill all regressions except one reviewed cleanup-only equivalence. Full Python regression passes with 2,113 tests and 91.43% combined coverage; hosted Windows/mutation confirmation will rerun after push.
- [x] TASK-090 aligns common Python decision-ID forms and malformed-JSON handling in Rust storage, and adds bidirectional shared-database checks for Rust decision writes, tier-aware statistics, and Python/Rust snapshots.
- [x] TASK-091 matches Python user-name precedence and POSIX account fallback, aligns persisted JSON integers to Rust's exact signed/unsigned 64-bit range, rejects out-of-range integers and non-finite values before persistence, and verifies concurrent writes plus malformed/non-object payload handling. Twenty-nine storage compatibility/concurrency checks, eleven Rust storage tests, and the full regression pass; the Windows fallback-test correction passes hosted Rust/Python compatibility on Windows.
- [x] TASK-092 adds Rust OpenAPI canonicalization, stable Unicode JSON serialization, and bounded `$ref` validation with differential coverage against the live contract plus external, missing, and cyclic references. Six focused differentials, the full Rust workspace, strict Clippy, and all 2,143 Python tests pass locally. Baseline validation, safe artifact export, manifest provenance, semantic compatibility classification, and unified CLI support remain open.
- [x] TASK-093 ports trusted-baseline loading to Rust with typed failure categories for missing, unreadable, too-deep, non-OpenAPI, invalid-reference, and oversized inputs. Nine contract differential tests, the full Rust workspace, strict Clippy, and all 2,146 Python tests pass locally. Safe artifact export, semantic compatibility classification, and CLI integration remain open.
- [x] TASK-094 adds a separately named Rust surface-diff probe with exact Python report comparisons for version/path/method changes, operation metadata, body requiredness, response status additions/removals/refinements, and summary/description changes. The Rust probe is intentionally partial and not a release gate; parameter, schema, media-type, security, safe export, manifest provenance, and unified CLI parity remain open. Hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `b847083`.
- [x] TASK-095 extends the Rust contract surface diff to server URL changes, inherited/operation-level authentication alternatives, and security-scheme add/remove/change reporting with exact Python report comparisons. Hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `b847083`.
- [x] TASK-096 ports parameter presence and requiredness classifications (additions, removals, optional/required transitions), preserving Python's report details and severity; hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `b847083`.
- [x] TASK-097 ports request and response media-type addition/removal classification while preserving the Python paths and report details; hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `b847083`.
- [x] TASK-098 adds bounded inline request/response schema comparison for type changes, property additions/removals/requiredness, and array-item type changes; hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `b847083`.
- [x] TASK-099 extends inline schema analysis to enum/const sets, numeric and size bounds, patterns, formats, defaults, and `additionalProperties`, including Python-compatible equality and exact mixed integer/float ordering; hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `b847083`.
- [x] TASK-100 follows bounded local schema `$ref` aliases through request and response definitions, nested properties, and recursive schemas; hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `b847083`.
- [x] TASK-101 applies the same schema and `$ref` analysis to matching operation parameters, including type changes, patterns, enum narrowing, newly declared schemas, and simultaneous requiredness changes; hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `b847083`.
- [x] TASK-102 ports nullable schema wrappers, OpenAPI `type` unions, `anyOf`/`oneOf` alternative direction, `allOf` conjunction direction, stable branch pairing, `$ref` expansion inside union branches, and the matching 64-level expansion boundary. Eleven focused union/depth cases and all 66 contract differential cases pass. The full Python suite passes (2,203 passed, 5 skipped), the full Rust workspace and strict Clippy pass, and coverage is 92.76% statement, 88.35% branch, and 91.75% combined. Hosted Rust/Python compatibility passes on Linux, Windows, and macOS at `a7f3099`; the complete semantic analyzer and unified CLI integration remain open.
- [x] TASK-103 adds Rust canonical OpenAPI export and a provenance manifest with product/API versions, source commit, generated time, tool identity, and operation count. Four focused Python/Rust export checks cover canonical bytes, stable manifest fields, symlink/hardlink refusal, and linked-parent refusal. The full Rust workspace, strict Clippy, formatting, Ruff, all 70 contract compatibility checks, and the full Python regression pass locally. Hosted Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `5251a1b`; the full semantic analyzer and unified CLI integration remain open.
- [x] TASK-104 starts the Rust plugin-system port with the exact Claude Code/Codex inventory, bounded error echoing, destination-root precedence, and portable path validation; four Rust unit tests and three Python/Rust differential tests cover metadata, host paths, whitespace, Unicode, traversal, device names, and line-injection attempts. The 2,210-test local Python regression and hosted Rust/Python compatibility on Linux, Windows, and macOS pass. This closes the manifest/path trust-boundary slice only; filesystem transactions, ownership records, install/uninstall, diagnose/doctor, and the user-facing `agentrouter plugin` commands remain Python-only.
- [x] TASK-105 validates the Rust plugin ownership-record JSON shape, known dispositions, safe relative destinations/backups, digest fields, and integer file/directory identities. Six Rust plugin unit tests, four Python/Rust differentials, and the 2,211-test Python regression pass locally, including Python's accepted bool-as-int and `2.0 == 2` behavior. It does not yet read state from disk, verify digests/inodes, or permit mutation; the no-follow reader and transaction protocol remain open. Hosted confirmation is recorded with TASK-106.
- [x] TASK-106 adds the read-only Rust `agentrouter plugin list` command. It compares output with Python for absent/present and linked destinations; traversal refuses links/reparse points. Rust workspace and non-skipping Python/Rust compatibility jobs pass on Linux, Windows, and macOS at `f81d2d1`.
- [x] TASK-107 adds a no-follow ownership-state reader using pinned root/private-directory handles, single-link checks, stable identity/size/mtime verification, schema validation, and SHA-256 provenance. Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `f81d2d1`.
- [x] TASK-108 adds read-only Rust `agentrouter plugin doctor` text and JSON output, with Python-compatible findings for missing, unmanaged, managed, corrupt-state, and linked destinations. Cross-platform Rust workspace and non-skipping Python/Rust checks pass at `f81d2d1`.
- [x] TASK-109 adds Rust `agentrouter plugin install NAME --dry-run` with Python-compatible create, preserve, adopt, managed-skip, overwrite, and blocked actions; the preview performs no writes. Cross-platform hosted checks pass at `f81d2d1`. macOS fixture roots are canonicalized while production link checks remain fail-closed.
- [x] TASK-110 ports Rust no-force plugin installation for missing and byte-identical files and persists Python-compatible ownership state. The subsequent TASK-113 slice adds forced replacement and transaction recovery; Windows hosted validation is tracked below.
- [x] TASK-111 removes the annotation manifest's signed-64-bit ceiling with exact arbitrary-precision integer preservation for schema versions and count maps. Focused schema/store/CLI differentials (71 cases), full Python regression, Rust workspace, strict Clippy, formatting, Ruff, and diff checks pass locally. Hosted Linux/Windows/macOS Rust/Python checks pass at `132151d`. YAML serializers reject unsupported oversized integer narrowing instead of silently losing precision. Datetime grammar and other schema edges remain Partial.
- [x] TASK-112 ports Rust plugin uninstall with exact ownership checks, backup restoration, historical managed paths, and empty-directory cleanup; included in the subsequent TASK-113 full lifecycle verification.
- [ ] TASK-113 adds forced replacement and identity-checked Rust transaction recovery compatible with Python journals. The native handle-relative rename and Windows strict Clippy pass in hosted Rust workspace checks. The Windows compatibility suite found the Rust lock path reads the lock byte before waiting; it now defers that read until the exclusive lock is held and has detailed failure output. The fix awaits hosted compatibility revalidation.
- [ ] TASK-114 adds journaled Rust managed-payload upgrades while preserving Python ownership and original-backup metadata. Seven Rust crash-recovery tests, the full Rust workspace, strict Clippy, and the full Python regression pass. The complete mutation campaign passes at 0.9698 overall with zero unreviewed survivors; exact numbers are in [`docs/MUTATION_REPORT_2026-11-14-TASK-114.md`](docs/MUTATION_REPORT_2026-11-14-TASK-114.md). Hosted Linux/Windows/macOS validation remains pending.
- [x] TASK-115 completes the Rust performance smoke evaluator contract: default tasks, packaged seed loading, classifier injection, aggregate-runner task reuse, and stable report fields. Six Python/Rust performance checks, the full Rust workspace and strict Clippy pass locally. The full Python regression and coverage also pass; hosted cross-platform confirmation remains part of the release candidate check.
- [x] TASK-116 adds default seed-catalog loading to the Rust provider evaluator while preserving the existing explicit-catalog JSON probe. Both focused Python/Rust cases and the refreshed full Python suite pass locally; hosted cross-platform confirmation remains part of the release-candidate checks.
- [x] TASK-117 aligns the Rust routing evaluator with Python's last-entry behavior for duplicate model keys. A differential fixture reproduced the mismatch before the fix and passes after it.
- [x] TASK-118 adds Rust classifier injection paths for the Python routing and safety evaluator seams. Complete Python regression passes with 2,268 tests and 4 skips; the routing and safety evaluator modules now meet the differential parity bar. The full Rust workspace, strict Clippy, formatting, Ruff, and diff checks pass locally; hosted Windows confirmation is pending.
- [x] TASK-119 matches legacy gold loader errors and Python's ASCII-escaped JSON artifacts; focused differentials, the full Rust workspace, strict Clippy, formatting, Ruff, and diff checks pass. Full Python regression passes with 2,268 tests and 4 skips; Windows plugin filesystem validation remains tracked under TASK-113.
- [x] TASK-120 adds empty, partial, duplicate, extra, and complete command/group inventory differentials for the Rust CLI platform evaluator. Four focused Python/Rust cases pass; the Rust unified CLI's live surface and the production grader wiring are still under CLI parity work.
- [ ] TASK-121 exposes guided `setup` and the `evaluate` legacy-gold alias through the unified Rust CLI, with preference persistence, host discovery, local sample routing, custom-config preservation, and credential redaction coverage. Linux Rust workspace tests, strict Clippy, focused setup/evaluate, artifact, and process-lock tests pass locally; the full Python suite now passes 2,308 tests with 4 skips. Hosted Windows validation found an unstable `MetadataExt::number_of_links` call in config safety checks; setup now queries link count and reparse flags through `GetFileInformationByHandle`, retaining fail-closed behavior. Windows strict Clippy also caught the Unix-only lock path parameter; both fixes are pushed, with hosted revalidation running.
- [ ] TASK-122 replaces the Rust doctor's placeholder plugin warning with the existing safe Rust plugin diagnostics, aggregates blocked/attention findings like Python, and reports the built-in Rust REST API as available. Thirteen Python/Rust diagnostic compatibility cases pass, including missing and corrupted plugin destinations; the full Rust workspace and strict Clippy pass locally. Cross-platform CI is pending.
- [ ] TASK-123 corrects annotation timestamp parity for ISO datetimes with omitted seconds and a `Z` suffix, including lowercase `z`. The differential test now sends raw timestamps to Rust rather than pre-normalizing them through Pydantic. All 54 annotation schema compatibility cases, the full Rust workspace, and strict Clippy pass locally; cross-platform CI is pending.
- [x] TASK-124 aligns the three Rust registry date fields with Pydantic `date | None` normalization for YAML date scalars, midnight ISO datetimes (fractional/offset forms included), and integer, float, or numeric-string epoch dates. Non-midnight datetimes, malformed offsets, booleans, and fractional epoch instants remain rejected. The complete Python suite passed 2,308 tests with 4 skips and 49 registry cases; the focused registry suite now passes all 50 cases, including malformed Unicode without panicking. Rust workspace tests and strict Clippy pass locally. Cross-platform CI for the resulting commit remains pending.
- [x] TASK-125 aligns Rust registry scalar coercion with Pydantic for bounded integer, float, and boolean fields. The hosted follow-up at `6223871` passes Rust workspace and Python/Rust compatibility on Linux, Windows, and macOS. The initial 593e375 regression was fixed with a visitor for arbitrary-precision JSON numbers and YAML rejection of the reserved marker map. The unchanged promotion gate remains blocked by the frozen context score.
- [x] TASK-126 aligns Rust Classification confidence and boolean scalar coercions with Pydantic, and matches the whitespace boundary for underscored float strings in registry values. Twenty-two focused compatibility tests and the full local regression pass. Hosted Rust and Python/Rust checks pass across Linux, Windows, and macOS at `2e14606`; the frozen release gate remains unchanged.
- [x] TASK-127 removes the Rust `Classification.context_tokens` width mismatch and aligns numeric, string, and boolean coercions across classification, routing, HTTP, and MCP paths. Its 295 focused Python/Rust/API differentials, full Python suite, Rust workspace, strict Clippy, formatting, Ruff, Bandit, pip-audit, and cargo audit pass; hosted Rust and Python/Rust checks pass across Linux, Windows, and macOS at `4a3e7ab`.
- [x] TASK-128 preserves unbounded positive `ModelEntry` token limits through YAML/JSON registry loading, OpenRouter refresh, route scoring, evaluation, display, and guarded OpenAI output capping. Full regression passes 2,382/4; Rust workspace, strict Clippy, Rust 1.89, formatting, Ruff, Bandit, pip-audit, and cargo audit pass locally. Hosted Rust and Python/Rust checks pass on Linux, Windows, and macOS at `04c483d`; the unchanged promotion gate remains blocked.
- [x] TASK-129 enforces the public Rust `Ability` type's Pydantic 0–10 bounds at direct deserialization, not only when nested under a registry model. Ten accepted/rejected differential values are covered; 88 focused registry/schema compatibility cases and 23 registry crate tests pass. Full regression passes 2,392/4 at 91.970% statement, 87.690% branch, and 90.988% weighted combined; full Rust workspace, strict Clippy, formatting, and Ruff pass. Hosted Rust and Python/Rust checks pass at `83fd7dc`; the frozen gate remains blocked.
- [x] TASK-130 adds direct Rust/Python roundtrip coverage for public `ExecutionTarget` and `Provider` schema classes, including defaults, coercions, enum selection, required fields, unknown fields, and invalid values. Focused schema/registry suites pass 101 cases; full regression passes 2,405/4 with 91.970% statement, 87.690% branch, and 90.988% weighted combined coverage. Full Rust workspace, strict Clippy, format, Ruff, and diff checks pass locally; hosted Rust and Python/Rust checks pass across Linux, Windows, and macOS.
- [x] TASK-131 directly checks every declared value of all twelve public `agentrouter/schema.py` enums against Pydantic, plus invalid strings, nulls, and numbers. All 104 focused schema cases and the full 2,486/4 Python regression pass, at 91.970% statement, 87.690% branch, and 90.988% weighted combined coverage. The formatting correction passes; hosted Rust, Python/Rust compatibility, Python 3.10–3.13, macOS, and Windows checks pass at `16c0a04`.
- [x] TASK-132 directly checks `ModelEntry` defaults, all required fields, Pydantic-compatible scalar coercions and bounds, dates, nested execution targets, serialization, and derived properties. It deliberately tightens Python validation to reject non-finite registry prices and confidence, matching Rust. Focused schema/registry compatibility: 211 passed; full regression: 2,509 passed / 4 skipped with 91.970% statement, 87.690% branch, and 90.988% weighted combined coverage. Full Rust workspace, strict Clippy, Rust format, Ruff, and diff checks pass. Hosted Rust and Python/Rust compatibility, Python 3.10–3.13, macOS and Windows suites pass at `ea1f875`; only the frozen gate fails.
- [x] TASK-133 closes the direct public-schema inventory: Classification defaults, all eight required fields, populated optionals, and alternative enum; omitted defaults and required fields across Ability, ExecutionTarget, Provider, and ModelEntry; plus both infinities rejected for model ability confidence. Focused schema/registry/classification compatibility: 260 passed. Full regression: 2,525/5 with 91.970% statement, 87.690% branch, and 90.988% weighted combined coverage. Full Rust workspace, strict Clippy, formatting, Ruff, and diff checks pass. Hosted Rust/Python checks pass at `4909abd`; only the frozen gate fails.
- [x] TASK-134 migrates the Python MCP adapter to SDK 2.x/current stateless protocol for Python 3.11+ while retaining SDK 1.x/legacy protocol on Python 3.10; Rust now handles `server/discover`, per-request version checks, server identity metadata, unsupported versions, and the legacy initialize handshake. The five planning tools still expose no execution capability. Focused MCP suites pass on Python 3.10/MCP 1.30 and Python 3.11/3.12/MCP 2.3 (23 each); full Python passes 2,525/5, and full Rust workspace, strict Clippy, format, Ruff, and wheel build pass. Both hosted MCP SDK jobs and all Rust workspace platform jobs pass at `a900126`; Linux Python/Rust compatibility also passes while the remaining matrix completes. The module remains Partial for non-stdio transports and broader lifecycle coverage.
- [x] TASK-135 closes `agentrouter/server/limits.py` behavioral parity: Rust/Python differential tests now compare keyed concurrency, success replay, non-2xx and error recomputation, and independent keys. Eight focused cases, full Rust workspace, strict Clippy, format, Ruff, and diff checks pass locally. The full Python suite passes 2,529/5 at 91.971% statement, 87.690% branch, and 90.988% combined coverage; see [`docs/COVERAGE_REPORT_2026-11-14-TASK-135.md`](docs/COVERAGE_REPORT_2026-11-14-TASK-135.md). At `934fe17`, push-workflow MCP, Rust workspace, Python/Rust compatibility and completed Python-version/macOS checks pass; one Windows job and duplicate PR-workflow jobs are still running. Python's asyncio lock shape maps to Rust's keyed compute API while preserving observable behavior.
- [x] TASK-136 adds `serve_app`/`serve_router` and an owned `RunningApp` lifecycle to Rust reliability. Six focused Python/Rust compatibility cases pass, including `/health` load, graceful/idempotent stop, and closed-port verification; Rust workspace tests, strict Clippy, and formatting pass locally. Hosted Rust workspace and Python/Rust compatibility pass on Linux/Windows/macOS at `ae47a76`. TASK-137 now supplies the user-facing soak command; transport exception naming remains a harness parity gap.
- [ ] TASK-137 adds the user-facing `agentrouter reliability soak` command. It initializes a non-clobbering home, clears the live API key in its local process, runs the Rust API on loopback, records repeated `/v1/route` batches, writes JSON to stdout/`--out`, and returns a failure code on server or transport errors. Eight focused reliability tests and the full Python suite (2,532 passed, 5 skipped) pass locally; coverage remains 91.971% statement, 87.690% branch, and 90.988% combined in [`docs/COVERAGE_REPORT_2026-11-14-TASK-137.md`](docs/COVERAGE_REPORT_2026-11-14-TASK-137.md). Full Rust workspace/Clippy, formatting, Ruff, and diff checks pass locally. Hosted checks are running. The harness remains Partial for rare generic I/O direction and exact Python module invocation.
- [x] TASK-138 matches the five names re-exported by `agentrouter.reliability.__init__` to a compiled Rust package export list. Nine focused reliability compatibility tests, the full Rust workspace, strict Clippy, Rust formatting, Ruff, and diff checks pass locally. Only the initializer export row is Parity; harness and soak behavior remain Partial where transport errors are ambiguous. Hosted validation is running at `b9559ac`.
- [ ] TASK-139 maps common Rust transport failures to Python-compatible categories. The 52c9565 Windows failures showed a just-closed ephemeral port can be filtered as a timeout; a later Windows run showed port zero may also fail to produce a transport exception. The cross-platform test now uses an unsupported URL scheme and confirms `UnsupportedProtocol` before socket access; the focused check passes locally. `ureq` still does not distinguish every generic read/write I/O failure; hosted validation follows the next push.
- [ ] TASK-140 exercises all nine Rust SDK endpoints against the Python SDK and a shared local HTTP fixture. Three scenarios cover authenticated, absent, and blank API keys; exact methods, paths, JSON bodies, response decoding, structured API errors, trailing-slash base URLs, and explicit zero/empty optional values match. Rust workspace and security checks pass on all platforms. TASK-141 extends transport injection and error-category parity; Windows compatibility repair is awaiting the next hosted run.
- [ ] TASK-141 adds a public Rust SDK transport trait, explicit timeout propagation, typed error categories, and idempotent close. TASK-147 explicitly applies the configured timeout to TCP connection setup while preserving the overall deadline. Python `httpx.MockTransport` and Rust fixture transport compare all nine operations, including body, auth-header presence, content type, timeout settings, and responses; four injected exception categories match. Malformed fixture configuration fails closed; diagnostics redact URL credentials and bodies; close waits for active sends and drops the default agent. TASK-147's focused SDK tests (10 Rust, 41 Python differential), full Rust workspace, strict Clippy, formatting, Ruff, and diff checks pass locally. SDK parity remains Partial for native timeout-model and generic I/O differences; hosted validation awaits push.
- [ ] TASK-056 adds the `agentrouter-evaluate` Rust CLI for listing/validating datasets, running fixture profiles, writing/rendering/comparing reports, availability, explicit external prepare blockers, and context-band generalization. Four smoke/differential tests pass. The Rust command does not yet replace the Python `agentrouter evaluate` surface or load real datasets, so CLI module parity remains Partial.
- [x] PR #31 upgraded bundled SQLite to 3.54.1, replaced `unsafe-libyaml`, and raised the Rust minimum to 1.89; workspace tests, Clippy, security audit, and cross-platform CI passed before merge at `a246cf6`.
- [x] Website product-truth fixes, font hierarchy/motion redesign, unused shadcn CLI removal, server limits/API tests, and website lint/build CI merged via PR #27. npm build/lint and production dependency audit passed; full npm audit still reports moderate dev-tool advisories.
- [x] Benchmark evidence merged via PR #29: 12/12 routing gold scenarios and 15 focused tests; live latency/cost are explicitly not claimed.
- [ ] Full Rust parity is not complete: R4 public CLI and full storage-contract coverage remain; HTTP/MCP, provider execution, hosted validation for managed plugin upgrades, evaluation adapter base/runner/annotation, and R5-R13 remain. The full 77-file module inventory is in [`docs/RUST_PARITY_MATRIX.md`](docs/RUST_PARITY_MATRIX.md).

## Needs Krish

- Human evaluation: follow [`TASK_012_OWNER_ACTIONS.md`](TASK_012_OWNER_ACTIONS.md). Assign annotators A and B plus an adjudicator; run `agentrouter dataset pack --annotator A --seed 101 --out packs/pack_A.yaml` and `agentrouter dataset pack --annotator B --seed 202 --out packs/pack_B.yaml`; have each person independently run `agentrouter dataset annotate packs/pack_A.yaml --annotator A --out labels/annotator_A.jsonl` or the B/pack_B equivalent and label all 63 cases; have the adjudicator return `adjudications.json`; then run the documented dataset build and dev comparison. Only after that, evaluate the new private holdout once per candidate. Do not use AI labels or tune against the frozen holdout.
- OpenAI live validation: provide `OPENAI_API_KEY` through a local environment or a protected secret store and authorize one bounded Responses API smoke request, which may incur usage charges. Offline request/response fixtures are ready; no key is stored in the repository.
- Production release/deployment: after the local and hosted release gates pass, provide the production hosting/domain credentials and authorize any paid infrastructure and deployment. The Rust server is loopback-only and no production deployment has run.

Latest completed full local verification: Python 3.12 passes 2,733 tests with 7
skips on pytest 9.0.3 in 404.04 seconds. The committed coverage evidence remains
92.052% statement, 87.756% branch, and 91.064% combined, above required
thresholds; evidence is in
[`docs/COVERAGE_REPORT_2026-11-14-TASK-150.md`](docs/COVERAGE_REPORT_2026-11-14-TASK-150.md).
The run includes the API large-integer response differential, nested JSON
redaction, route-envelope cases, and earlier regressions. Rust workspace tests
pass locally, as do API crate tests, strict API Clippy, the full API schema
differential selection (57 tests), Rust formatting, Ruff, and `git diff --check`.
The pushed code head `d98caa2` completed fresh hosted validation after
the macOS root-alias repair, bundle-parent hardening, and evidence checkpoint; prior Rust workspace OS jobs and Linux
and macOS Python/Rust compatibility; Windows compatibility and most Python jobs
were running at the time of this update. PR #16's enforcing gate continues to
fail honestly at frozen context-band accuracy 0.6667 < 0.90. Human annotation,
live OpenAI validation, deployment credentials, and GitHub PR reviews remain
open; no threshold or holdout was changed.

PR #16 was reviewed against its release contract and code standards: no
separate implementation defect was identified in the reviewed diff, but the
PR is not releasable. Its immutable context-band accuracy is 0.6667 against the
unchanged 0.90 threshold; required independent human annotation is still open.

Historical PR audit: all merged PRs through #33 are present on the release
candidate. Closed PR #21 has no remaining file diff; its venv-pinned hook fix is
already present in the candidate. Closed PR #26 has only an obsolete Rust R1/R2
verification paragraph and a Cargo manifest newline relative to the candidate;
its registry implementation is already present. Closed draft PR #1 adds Python
unit tests only; current execution, routing-control, host-state, safety, and
mutation suites cover those behaviors, so the old test branch is not merged as
code. PR #16 remains the sole open PR.
