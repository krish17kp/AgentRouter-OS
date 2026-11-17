# Quality Dashboard — AgentRouter OS

## Current checkpoint — 2026-11-17

At pushed RC head `71408b2`, the macOS root-alias repair is recorded with the bundle
hardening evidence and the hosted Rust/Python matrix is green; TASK-175 repaired
the Windows diagnostics path-format mismatch. Local Python/Rust release checks remain green; the
frozen context-band gate and owner-supplied validation/deployment inputs remain
open.

TASK-183 adds fresh local release evidence: `cargo build --release --locked
--workspace` succeeds, the optimized binary reports `0.5.0rc1`, and
`cargo audit --no-yanked` reports no vulnerabilities across 207 locked crates.
RustSec does report one unmaintained `chrono` warning with no available fixed
upgrade; it is recorded in the dependency-audit note and is not hidden.

TASK-179 closes a concrete evaluation CLI contract gap: Rust `prepare --all`
now returns success after a complete external-blocker report, while a single
unavailable dataset remains a nonzero readiness result. All eight blockers are
reported explicitly and no fixture fallback is introduced. The evaluation
crate and direct command verification pass; the evaluation module remains
Partial for real-data loaders and orchestration.

TASK-180 closes the remaining human-readable context-band report differences:
bootstrap macro-F1 CI, Python-compatible containers, unquoted checksum, and
signed delta now match Python. JSON output is unchanged and strict Rust checks
pass; the evaluator remains Partial for external data and runtime orchestration.

TASK-181 tightens the Rust SDK's native timeout contract by applying the
configured bound independently to connect, read, write, and aggregate request
phases. Focused SDK tests, workspace Clippy, and formatting pass; native
read/write error classification remains Partial.

TASK-182 makes reliability response handling consume bodies before counting
statuses. A real truncated-body loopback probe now matches the Python behavior
of reporting a transport failure instead of a false success; broader
process/runtime parity remains Partial.

TASK-184 adds the same real-socket regression to the SDK client itself: a
declared-length truncated response is classified as `ReadError`, never as an
API result. Focused SDK verification, strict Clippy, formatting, and diff
checks pass; native read/write phase taxonomy remains Partial.

TASK-185 hardens plugin diagnosis for symlinked roots. The Rust doctor now
returns a path-specific blocked finding rather than an internal-error message,
matching the Python safety contract; focused regression and local smoke pass.

TASK-186 confirms the website's lint, production build, and production-only
dependency audit. The generated bundle is locally valid with zero production
vulnerabilities; deployment remains gated on hosting credentials/approval.

TASK-187 confirms the Python sdist/wheel build and isolated-wheel smoke. The
packaged CLI reports `0.5.0rc1` and can initialize and route from a clean home;
publication remains gated on the PyPI trusted publisher setup.

TASK-188 confirms the focused SDK/reliability/plugin/diagnostics compatibility
regression: 77 isolated Python/Rust tests pass in 26.33 seconds.

TASK-189 confirms the release SBOM path: CycloneDX 1.6 JSON generation passed
with 46 components from the declared optional dependency set.

TASK-190 adds the concrete Rust evaluation adapter facade and focused fixture
lifecycle tests. Metadata, availability, load, prepare, sample, validate,
checksum, and describe are covered; real HuggingFace loading remains an
explicit external blocker and the two parity rows remain Partial.

TASK-191 adds focused MCP input-hardening tests for malformed JSON-RPC and
invalid tool arguments. The safe five-tool surface is unchanged; broader
transport/lifecycle parity remains Partial.

TASK-192 confirms the complete isolated Python suite is green at 2,735 passed,
7 skipped, and one existing Starlette/httpx deprecation warning in 449.37
seconds.

TASK-193 confirms the optimized locked Rust workspace build and binary
version/help smoke. The 205-dependency audit has no vulnerability advisories;
the known unmaintained-`chrono` warning has no fixed upgrade.

TASK-194 confirms ordered lazy callable factories construct all eight Rust
adapter facades, matching the Python registry construction surface.

TASK-195 confirms the optimized binary's fresh-home `init`, route, doctor,
version, and five-tool MCP stdio smoke.

TASK-196 confirms 17 offline adapter/base Python/Rust differential tests pass;
real external dataset loading remains intentionally blocked.

TASK-173 hardens diagnostic bundle writes with no-follow parent creation, a
pinned capability directory, and exclusive creation. Serialized snapshots,
symlink/hard-link, directory-swap, and nested-parent regressions pass; focused
bundle/diagnostics checks and strict Clippy pass. Full bundle parity remains
Partial.

TASK-176 closes the `agentrouter/__main__.py` parity row with a direct
`python -m agentrouter --help` versus Rust unified-binary help/version
differential. Inventory: 60/77 Parity, 17 Partial.

TASK-177 aligns stable bundle environment metadata with a shared version field
and explicit Rust runtime marker; interpreter-specific metadata remains partial.

TASK-178 fixes evaluation CLI `status` to emit the actual real-loader
availability flag and matching blocker text. The focused evaluation CLI suite
passes 19 tests.

TASK-172 aligns Rust doctor stable summaries with Python and adds a direct
cross-language check. Diagnostics compatibility passes 41 focused checks and
strict Clippy; runtime-specific and full bundle parity remain Partial.

TASK-171 closes provider refresh parity after independent security review. Rust
refresh now uses no-follow registry traversal, fixed HTTPS endpoints, bounded
header-only transport, Python-compatible OpenRouter/OpenAI mapping, provenance,
deprecation warnings, dry-run, and atomic generated-file replacement. A
feature-gated fixture transport supports deterministic process differentials
without exposing a production URL override. Full Rust workspace/strict Clippy
and Python regression (2,733 passed, 7 skipped) pass. Inventory: 59/77 Parity,
18 Partial.

TASK-170 closes packaged annotation CLI parity after independent review. The
Rust evaluator embeds the candidate pool and frozen holdout, prefers checked-out
files for source-tree development, and falls back to embedded bytes elsewhere.
Exact resource hashes/counts and source-independent fallback are tested;
annotation CLI/schema compatibility passes 88. Inventory: 58/77 Parity,
19 Partial.

TASK-169 closes the HTTP application lifecycle row after independent review.
The executable now uses the shared OS-aware home resolver; process-level
differentials cover request-ID guarantees on auth/rate/CORS short circuits,
generic registry errors with one redacted log, and non-cached validation
idempotency responses. Focused HTTP/schema compatibility passes 114, full Rust
workspace/Clippy passes, and full Python regression passes 2,731/7. Inventory:
57/77 Parity, 20 Partial.

TASK-168 closes the observability module after independent security review.
Rust now provides task-local request context with synchronous setter/scoped
guard compatibility, opt-in logging configuration, generic events, bounded
strictly redacted API errors, active OTel spans, and one-record server error
paths. Focused observability tests (9), full Rust workspace/Clippy, and the
full Python regression (2,728 passed, 7 skipped) pass. Inventory: 56/77 Parity,
21 Partial. HTTP service errors intentionally retain bounded message-only
evidence because no traceback object crosses the blocking boundary.

## Previous checkpoint — 2026-11-16

TASK-167 closes server-service parity after adding home/registry and direct-call
facades, fail-closed raw argument handling, active OpenTelemetry route spans,
correlated direct-service logging, and full service differentials. Focused 102,
full Rust workspace/Clippy, and Ruff pass; full Python regression is running.
Full Python regression passes 2,728/7. Inventory: 55/77 Parity, 22 Partial.

TASK-166 closes annotation-schema parity after repairing a public-deserialization
validation bypass found by independent audit. Constants, required/default/null,
unknown and nested fields, agreement edges, arbitrary integers, scalar coercion,
and expanded datetime boundaries pass 77 direct and 108 production-path checks.
Evaluation Rust tests, strict Clippy, and Ruff pass. Inventory: 54/77 Parity,
23 Partial. Full Rust workspace/Clippy and Python 2,719/7 pass.

TASK-164 closes request/response schema parity after independent audit. Public
constants, defaults, coercions, bounds, extra-field behavior, passthrough and
owned response shapes, arbitrary-precision integers, and non-BMP Unicode length
boundaries are covered differentially. Focused 93, API Rust tests, strict Clippy,
and Ruff pass. Full Python regression passes 2,696/7. Inventory: 53/77 Parity,
24 Partial.

TASK-162 closes runner parity with owned runtime discovery, Python-compatible
selection/error ordering, bounded concurrently drained provenance commands, and
a documented runtime-specific environment contract. Independent audit is clear;
full Rust workspace/Clippy, Ruff, 40 focused checks, and full Python 2,660/7 pass.
Inventory: 52/77 Parity, 25 Partial. TASK-161 hosted Rust migration CI passes on
Linux, Windows, and macOS; its enforcing release gate remains honestly held.

TASK-165 addresses the subsequent Windows Python failures at their platform
roots. Local focused 46, Ruff, strict Clippy, and independent review pass;
hosted confirmation is pending.

TASK-161 closes `agentrouter/evaluation/grading.py` after three audit findings
were repaired: classification now precedes dependency discovery, the default
full scorecard preserves Python's hidden platform-detail contract, and complete
deterministic reports are compared in both default and injected modes. Rust
workspace, strict Clippy, Ruff, 27 focused differentials, and full Python
regression pass (2,642 passed, 7 skipped in 343.42 seconds). The inventory is
51/77 Parity with 26 Partial. Hosted cross-platform validation is pending the
authorized RC push; production readiness remains held by the unchanged gates.

## Previous checkpoint — 2026-11-15

At `5af3c55`, the hosted Python 3.10–3.13, Windows/macOS Python, Rust
workspace, Python/Rust compatibility, API, build, security, website, and mutation
checks pass. The RC-to-main PR still fails the unchanged frozen context-band
gate at 0.6667 < 0.90, and live OpenAI smoke skips without credentials. TASK-152
adds privacy-safe Rust route logs; local full regression passes 2,590/5 at
92.052% statement, 87.756% branch, and 91.064% combined coverage. Rust workspace,
strict Clippy, wheel/sdist build, and clean-wheel smoke pass. Hosted TASK-152
checks await the RC push. The module remains Partial, as do 28 other rows.

## Previous checkpoint — 2026-11-14

At last pushed code head `9a7dc7a`, all Rust workspace OS jobs and Linux/macOS
Python/Rust compatibility pass; Windows Python/Rust compatibility and most
Python/platform jobs are still running. The PR workflow's enforcing gate fails
on frozen context-band accuracy 0.6667 < 0.90; the ordinary push workflow skips
that gate. TASK-150 is locally verified and awaits hosted checks. PR #16 has no
GitHub reviews.

The latest full Python regression passes 2,580 / skips 5. The TASK-150 coverage
report measures 92.030% statement, 87.712% branch, and 91.038% combined.
Evidence: [`docs/COVERAGE_REPORT_2026-11-14-TASK-150.md`](docs/COVERAGE_REPORT_2026-11-14-TASK-150.md).
TASK-140's Rust SDK
wire differential passes all nine endpoints across authenticated, absent, and
blank API-key cases. TASK-141 adds injected transport and timeout parity, four
matched HTTPX failure categories, malformed-fixture rejection, and client close
behavior; 52 focused SDK/reliability Python tests and nine Rust SDK unit tests
pass locally. TASK-142 and TASK-143 close evaluator seed-contract and runtime
platform-discovery gaps. TASK-144's non-2xx OpenAI status differential passes
68 Python tests and three Rust unit tests locally, and is pushed at `0d3ea70`.
TASK-145 adds three full-output CLINC150 real-row differentials. The parity
inventory now contains 50/77 full modules, with 27 Partial. TASK-147's focused
Rust SDK tests (10 Rust, 41 Python differential) and full Rust workspace pass
locally. Python remains the shipping authority and the Rust migration is
incomplete. TASK-149 compares recursive Rust JSON redaction with Python for
nested credentials and ordinary diagnostics; structured logging and tracing
remain outstanding. TASK-150 preserves arbitrary-precision API response context
windows across Python and Rust.

## Historical dashboard

_Last refreshed: 2026-08-08 (iter26, after TASK-011/012/013/014/015/016 merged to
the RC @ `5847c22`). Current measurements supersede historical TASK-004 in-sample
readiness claims._

| Dimension | Current state | Evidence |
|---|---|---|
| Python tests | Pass | `pytest` 684 passed, 3 env-skips (2026-08-08, local); includes TASK-011/012/013/015/016 tests; local env watchdog issue that previously killed multi-second runs is resolved |
| TypeScript SDK | Pass (prior session) | `npm test` 8/8 and `npm run typecheck`; unaffected by TASK-015 |
| Hooks | Pass | `.claude/hooks/test_hooks.py`: **33 passed** (git guardrail allow/block matrix) |
| Lint | Pass | Ruff check + format clean across the tree (verified 2026-08-08) |
| Dependency audit | Pass | `pip-audit -r requirements.txt`: no known vulnerabilities (2026-08-08) |
| Evaluation grade | ~98/100 | `python -m agentrouter eval run --all --out-dir artifacts/evaluation` |
| Evaluation gates | **6/7; release readiness NO** | Frozen 45-case context holdout accuracy 0.6667 (rules-active), below the unchanged 0.90 threshold |
| Mutation | **Pass** | Linux mutmut 3.6.0, 923 mutants: overall 0.9837; safety_policy_execution 0.985; routing_engine 0.9815; no safety/policy/execution-bypass survivor |
| Security | Pass | Bandit 0 (config-aware, verified locally 2026-08-08) + pip-audit green on RC CI |
| Packaging | Pass (re-verified 2026-08-08) | Wheel + clean-venv smoke outside the repo: `providers status/doctor/rollback/restore`, `route`, packaged resources |
| GitHub CI (RC) | Pass; enforce-release-gate correctly gated to promotion only | Matrix 3.10-3.13 + test-windows + build-smoke + Security + release-readiness-report + Critical Mutation Testing green on `5847c22`; `enforce-release-gate`/`live-smoke` skip on task/RC pushes by design (TASK-014) |
| Context-band dataset program | Delivered | TASK-011/012 merged (annotation CLI, adjudication, leakage-safe splits, comparison); final human labels are the external TASK-012 step |
| Catalog trust + reversibility | Delivered | TASK-013 + TASK-015 merged: provenance block, atomic refresh, deprecation reporting, rollback/restore, `providers doctor` |
| CI release-gate semantics | Delivered | TASK-014 merged: report/enforce split |
| Security review (TASK-015 diff) | Pass | Independent review: 0 critical, 3 medium, 2 low; all medium+low fixed and regression-tested (symlink-race, crash-on-corruption, backup-rotation data loss) |

## Canonical evaluation gates

- `task_type_macro_f1>=0.90`: PASS
- `high_risk_recall==1.00`: PASS
- `approval_accuracy==1.00`: PASS
- `tool_needs_f1>=0.90`: PASS
- `context_band_accuracy>=0.90`: **FAIL (0.6667; shipped rules-active)**
- `high_risk_gated==1.00`: PASS
- `synthetic_routing_top1>=0.95`: PASS

The former 0.945 context value is explicitly labeled as in-sample gold-set
accuracy in the current report. It is not evidence of held-out generalization.

## Open release blockers

- Frozen held-out context-band accuracy (0.6667) is below the unchanged 0.90
  threshold. This is the sole remaining blocker; it needs the human-labelled
  dataset from TASK-011 tooling + TASK-012 operations, not tuning.
- (Resolved) Linux mutation score: overall 0.9837, all gates pass.
- (Resolved) Full verification matrix + release-branch GitHub checks: green except
  the honest release-gate above.

## Planning boundary evidence — 2026-11-17

- Execution planner: 4 Rust unit tests passed; remote/API execution and all
  adapters remain disabled.
- Orchestration planner: 4 Rust unit tests passed; bounded DAG validation,
  deterministic groups, tool allowlists, and idempotency guards are present,
  but no dispatch or mutation is enabled.
- CLI plan integration: fresh-home init/route/save/plan optimized smoke passes;
  the JSON plan reports `execution_enabled: false`.
- Routing benchmark parity: matched local pure-routing runs show Rust p50 at
  0.78×/0.77×/0.63× of Python for 10/100/1,000 candidates; not an SLO.
- Rust-only runtime: Python-absent optimized init/route/plan/doctor/MCP smoke
  passes; no provider execution or deployment was performed.
- CLI plan regression: 1 focused process-level compatibility test passed,
  including explicit remote/approval flags remaining non-executing.

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

Focused bundle/observability: 95 passed, 1 skipped. Full Python: 2,604 passed,
7 skipped; 92.021% statement, 87.833% branch, 91.058% combined coverage.
Independent review, hooks 33/33, Bandit, build, and installed-wheel smoke pass.

## TASK-155 fail-closed holdout grading — 2026-11-15

Focused grading differential: 6/6. Evaluation compatibility: 40/40. Full Rust
workspace and strict Clippy pass. Full Python: 2,609 passed, 7 skipped; 92.021%
statement, 87.833% branch, and 91.058% combined coverage. Review is clear.

## TASK-156 consistent injected grading — 2026-11-15

Scorecard/evaluation compatibility: 42/42. Rust evaluation tests and strict
Clippy pass. Full Python: 2,610 passed, 7 skipped; 92.021% statement, 87.833%
branch, 91.058% combined. Independent review is clear.
## TASK-157 public grading runtime — 2026-11-15

Default Rust grading now loads packaged models and queries the installed CLI
without caller manifests; failed discovery stops evaluation. Focused
compatibility and full Python 2,613/7 pass. Release readiness remains held.
## TASK-158 evaluation CLI contracts — 2026-11-15

Evaluation CLI error exits and option rejection now match measured Python
behavior. Full Python regression passes 2,626/7; Rust workspace, strict Clippy,
Ruff, and independent review pass. Overall release readiness remains held.
## TASK-159 platform evaluator parity — 2026-11-15

Process-level installed-CLI discovery failures and bounded manifest consistency
now complement exact injected scoring differentials. Independent re-audit,
focused 12, and full Python 2,630/7 pass. Inventory: 49 Parity / 28 Partial.

## TASK-203 execution preflight — 2026-11-17

Execution planner: 5/5 tests pass. Locked workspace check and formatting pass.
The planner is read-only and fail-closed; guarded CLI execution now uses it as
preflight with explicit adapter readiness. No live provider request or local
command was run.

## TASK-204 orchestration input hardening — 2026-11-17

Five orchestration planner tests pass, including duplicate-dependency and
empty-side-effect rejection. Strict crate Clippy and formatting pass. No
workflow was dispatched or allowed to mutate a workspace.

## TASK-205 current release smoke — 2026-11-17

Optimized Rust-only smoke: init, route persistence, doctor, and MCP negotiation
pass; default unavailable-host planning blocks, explicit preview remains
`execution_enabled=false`. Release build/audit pass; no live provider call ran.
