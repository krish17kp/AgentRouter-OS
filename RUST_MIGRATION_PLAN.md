# Rust Migration Plan

> Companion to [AD-7 in ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md#ad-7--approved-rust-native-target-phased-behind-the-existing-contracts).
> The **Python implementation in `agentrouter/` is the current, shipping system**
> and remains release-gated exactly as today (see **Current production status**
> below). This document plans a phased, contract-preserving port to a
> Rust-native implementation. No Rust code exists yet; no Python code is
> deleted as part of this plan. See `AGENTROUTER_FOUNDATION_REVIEW.md` (session
> artifact, not committed) for the review this plan responds to, and the
> **Subsystem inventory** section below for the actual recursive read of
> `agentrouter/` this revision is built from (not assumptions from other docs).

## Terminology

- **CURRENT ACTIVE IMPLEMENTATION** — the Python code in `agentrouter/`. This is
  what ships, what CI gates, what `pip install` installs, and what every
  acceptance test in this plan is measured against.
- **COMPATIBILITY REFERENCE** — the same Python implementation, kept running
  (initially as the only implementation, later side-by-side with a ported Rust
  module) so every Rust module has a live oracle to diff against. Nothing is
  deleted from this role until the retirement criteria at the bottom of this
  document are met.
- **APPROVED TARGET** — the Rust-native implementation described by this plan.
  Approved as a direction by the owner (AD-7); no code exists yet.
- **CURRENT PRODUCTION STATUS** — see below. Independent of implementation
  language.

## Current production status

Per `AGENT_HANDOFF.md`'s Release truth section: **NOT RELEASE READY.**
`context_band_accuracy = 0.6667` against the unchanged `0.90` frozen-holdout
gate (the other six of seven evaluation gates pass). Closing this requires the
real two-human annotation round in `TASK_012_OWNER_ACTIONS.md`; no AI may act
as annotator or adjudicator, the frozen holdout must not be tuned against, and
the threshold must not be lowered. This is true regardless of implementation
language and is not changed by this document — nothing here claims or implies
a production deployment.

## Non-negotiables carried over unchanged

- CLI contract (`CLI_SPEC.md`), HTTP contract (`contracts/http/v1/`), MCP
  tool/resource names, the registry YAML schema, and the SQLite decision-log
  schema are **preserved exactly**. A Rust component is only considered a valid
  replacement for a Python one once it passes the *same* compatibility suite
  the Python component is gated on today.
- The seven evaluation gates (`loop/QUALITY_GATES.yaml`) are the release
  authority regardless of implementation language. A ported scorer must
  reproduce bit-identical numbers on the frozen 45-case holdout before it may
  replace the Python scorer as gate authority — "close enough" is a failed
  migration step, not a passing one.
- Mutation thresholds (95% safety/policy/execution, 85% elsewhere) continue to
  apply; `cargo-mutants`/`cargo-audit` are the candidate Rust tools but their
  thresholds must be independently re-validated, not assumed equivalent to the
  current `mutmut`/`bandit` baselines.
- No AI may annotate or adjudicate the frozen holdout, in either language.
  This policy is implementation-independent and is **linked, not restated**:
  see `TASK_012_OWNER_ACTIONS.md` for the actual procedure.
- Remote/real-agent execution stays **disabled by default** in every language.
  MCP exposes no execution tool today (`agentrouter/mcp_server.py` exposes
  only `route`, `classify`, `explain`, `list_models`, `list_hosts` — no
  execution capability) and the migration must not add one without fresh,
  explicit owner authorization recorded the same way any other owner-gated
  decision is recorded in this repo. High-risk tasks and non-auto approval
  states must never auto-execute, in either language.
- The TypeScript SDK (`sdk/typescript/`) is **not** rewritten in Rust. It stays
  as the client for whatever server (Python today, Rust eventually) serves
  the committed HTTP contract.

## Subsystem inventory (recursive read of the actual repo, 2026-10-13)

Status legend: **IMPLEMENTED** (shipped, tested, release-gated) ·
**PARTIAL** (real but incomplete, e.g. no live adapters) · **INTERFACE ONLY**
(contract/shape exists, no working backend) · **PLANNED** (docs describe it,
no code) · **MISSING** (not present at all) · **BLOCKED** (needs
owner/credential/infra action this session cannot take).

| Subsystem | Status | Evidence |
|---|---|---|
| **Task processing** | | |
| Classification (task-type, confidence) | IMPLEMENTED | `agentrouter/classifier.py` (874 lines, largest single module after `cli.py`/`contract.py`/`plugins.py`); rule-based per AD-4, 86-case test suite |
| Complexity scoring | IMPLEMENTED | `agentrouter/engine.py` (237 lines) — complexity-weighted scoring + explanation trail, confirmed in `AGENT_HANDOFF.md`'s TASK-020 discovery pass |
| Risk assessment | IMPLEMENTED | `agentrouter/safety.py` (34 lines, small and gate-critical — 95% mutation floor) + `agentrouter/controls.py` (131 lines) |
| Context/token estimation | IMPLEMENTED | `agentrouter/context_model.py` (174 lines) |
| **Routing** | | |
| Model registry (YAML-backed) | IMPLEMENTED | `agentrouter/registry.py` (144 lines), seed catalogs under `agentrouter/seeds/` |
| Provider registry / adapters | PARTIAL | `agentrouter/usage.py` (207 lines) models UNKNOWN/UNSUPPORTED/AVAILABLE/EXHAUSTED/ERROR but "honestly UNSUPPORTED for every real provider today, since no live-credentialed adapter is registered" (`AGENT_HANDOFF.md`) — credential-gated, tracked in `loop/BACKLOG.yaml` P2 |
| Selection / scoring / weights | IMPLEMENTED | `agentrouter/engine.py`, preference-vector hook per AD-2 |
| Policy filtering (pre-filter controls) | IMPLEMENTED | `agentrouter/controls.py` — `--vendor`/`--host`/`--model`/`--max-price`/`--stable-only`/`--available-only`, AD-1 |
| Fallback / explanations | IMPLEMENTED | `agentrouter/engine.py` explanation trail; `explain` MCP tool and CLI command surface it |
| Execution-host resolution | IMPLEMENTED | `agentrouter/hosts.py` (365 lines) — verified execution-host state machine per TASK-016 |
| Harness/environment identity | IMPLEMENTED | `agentrouter/harness.py` (50 lines) — introspective only: Claude Code via `CLAUDECODE`, CI via `CI`/`GITHUB_ACTIONS`, GENERIC/UNKNOWN otherwise; no tool guessing |
| **Execution** | | |
| Real agent-invocation adapters | MISSING | No module under `agentrouter/` invokes a real agent/model process. `harness.py` only *detects* which harness Claude Code is running inside; it does not start, monitor, or collect output from one. |
| Provider authorization / live credentials | MISSING (credential-gated, BLOCKED on owner) | `usage.py`'s state model exists but zero adapters are registered — owner action needed, not engineering |
| Execution start/monitor/output-collect/verify/cancel/timeout/retry/recover | MISSING | No code found; this is real, net-new scope, not a port target |
| Resource/budget limits, audit logging for execution | MISSING | `agentrouter/server/limits.py` (169 lines) exists but limits HTTP request size/rate, not agent-execution budgets — do not conflate the two |
| **Orchestration (multi-agent)** | | |
| Workflow/task decomposition | MISSING | No module named or shaped like a planner; `grep -ril "orchestrat\|multi.agent\|workflow"` across `agentrouter/` matches only incidental identifier substrings in `context_model.py`, `classifier.py`, `contract.py`, `evaluation/adapters/twinrouterbench.py` — none is an orchestration engine |
| Agent selection across a workflow | MISSING | Single-decision routing exists (`engine.route`); no multi-step/multi-agent planner |
| Dependency graphs, sequential/parallel execution, isolated workspaces, context handoff, intermediate verification, failure recovery, cancellation, result aggregation | MISSING | None of this exists in the codebase today. This is the largest genuine gap the prior foundation review under-scoped — see **Multi-agent orchestration architecture** below, which is net-new design, not a 1:1 Rust port of existing Python |
| **Codebase intelligence (Graphify)** | | |
| Graph build/query integration | MISSING on this machine | `AGENT_HANDOFF.md`: verified absent — `~/.local/bin` and `~/.venvs` have no `graphify`; historical node/edge counts are from 2026-08-20 and may be stale. Graphify is an external tool invoked via CLI/PATH, not a module inside `agentrouter/` — there is nothing in-tree to "port"; migrating it means re-establishing (or writing) an equivalent capability, which is a new scope item, not a module on the port-order table |
| **Extensibility** | | |
| Skills (dynamic discovery) | IMPLEMENTED | Shipped in PR #15 per `AGENT_HANDOFF.md`; `.claude/` treated as historical/reference only per `AGENTS.md` |
| Plugins (install/list/doctor/uninstall) | IMPLEMENTED | `agentrouter/plugins.py` (1309 lines, second-largest module) — transactional install/backup/restore, symlink/reparse-point/permission-bit hardening (TASK-019), atomic replace, per-key locking |
| MCP server (tools/resources) | IMPLEMENTED, intentionally execution-free | `agentrouter/mcp_server.py` (86 lines): `route`, `classify`, `explain`, `list_models`, `list_hosts` only — confirms the "MCP exposes no execution tool" invariant in `AGENTS.md` |
| Provider adapters | PARTIAL | See Provider registry row above |
| **Data** | | |
| SQLite decision log | IMPLEMENTED | `agentrouter/store.py` (214 lines) — WAL mode, `busy_timeout`, `store.snapshot` (EPIC-018 defects 1–2) |
| Registry YAML | IMPLEMENTED | `agentrouter/registry.py` + `agentrouter/seeds/` |
| Execution history | PARTIAL | Recorded via `store.py` decision log; no separate execution-history store exists because real execution doesn't exist yet (see Execution row) |
| Eval records | IMPLEMENTED | `agentrouter/evaluation/` (24 files, ~3,100 lines across `base.py`, `runner.py`, `grading.py`, `metrics.py`, `context_bands.py`, `schema.py`, `reports.py`, `cli.py`, adapters, evaluators) |
| Annotation datasets | IMPLEMENTED | `agentrouter/annotation/` (10 files — `candidates.py`, `packs.py`, `splits.py`, `store.py`, `schema.py`, `dedup.py`, `compare.py`, `adjudicate.py`, `graph_signals.py`, `cli.py`); frozen-holdout leakage guardrail in `splits.py`; blinding fix (PR #18) stripped `template`/`notes` from packs |
| **Interfaces** | | |
| CLI | IMPLEMENTED | `agentrouter/cli.py` (1754 lines, largest module) |
| HTTP API | IMPLEMENTED | `agentrouter/server/app.py` (326 lines) + `service.py`/`schemas.py`/`limits.py`; versioned contract per AD-5 |
| TS SDK compat | IMPLEMENTED (stays Python-server-agnostic) | `sdk/typescript/` — not in scope for Rust rewrite |
| MCP tools/resources | IMPLEMENTED | see above |
| **Operations** | | |
| Diagnostics (`doctor`) | IMPLEMENTED | `agentrouter/diagnostics.py` (339 lines) — unified `Check` pattern, TASK-018C |
| Logging/tracing | IMPLEMENTED | `agentrouter/observability.py` (276 lines) — correlation-ID tracing, secret-safe redaction |
| Metrics/dashboard | IMPLEMENTED | `agentrouter/dashboard.py` (98 lines) |
| Security (redaction, bundle) | IMPLEMENTED | `agentrouter/bundle.py` (207 lines) — 16 credential-format fixtures |
| Release validation | IMPLEMENTED | `agentrouter/contract.py` (1267 lines, third-largest module) — semantic HTTP compatibility gate, AD-5/AD-6 |
| Config | IMPLEMENTED | spread across `cli.py`/`registry.py`; no separate config module found |
| Packaging | IMPLEMENTED | `pyproject.toml`-driven wheel/sdist, verified clean-venv install smoke per `AGENT_HANDOFF.md` |
| Reliability/soak | IMPLEMENTED | `agentrouter/reliability/` (`harness.py` 187 lines, `soak.py` 175 lines) |

Module sizes (non-`__init__`, >100 lines) ordered smallest→largest for port
sequencing reference: `taxonomy.py`(66) < `harness.py`(50, listed for
completeness though under 100) < `annotation/graph_signals.py`(74) <
`evaluation/registry.py`(71) < `mcp_server.py`(86) < `annotation/store.py`(88)
< `annotation/splits.py`(89) < `dashboard.py`(98) < `annotation/adjudicate.py`
(101) ... up to `cli.py`(1754) > `plugins.py`(1309) > `contract.py`(1267) >
`classifier.py`(874) > `evaluate.py`(442) > `diagnostics.py`(339) >
`server/app.py`(326) > `refresh.py`(347) > `hosts.py`(365). Full listing is
reproducible with `wc -l agentrouter/**/*.py`.

## Target architecture — Rust workspace crate boundaries

Chosen by actual responsibility/dependency read above, not a blind 1:1 file
mapping. A modular monolith (one workspace, many crates, one deployable binary
plus one library), not distributed services — matching the "local-first,
offline-capable" invariant in `AGENTS.md`. Layering (classification / policy /
ranking / host resolution / execution planning / safety enforcement stay
distinct) is preserved as crate boundaries, not just module boundaries, so a
dependency-graph cycle is a compile error, not a code-review finding.

```
agentrouter-core        (shared types: Task, Decision, ModelSummary, errors — no logic)
  ^
  |-- agentrouter-classifier   (classification.py port: task-type, confidence)
  |-- agentrouter-registry     (registry.py + seeds: model/host facts, validated YAML)
  |-- agentrouter-policy       (controls.py, safety.py: pre-filter + risk gating)
  |     ^
  |     |-- agentrouter-routing    (engine.py: scoring, weights, explanation trail;
  |     |                           depends on classifier + registry + policy)
  |     |-- agentrouter-execution  (hosts.py, usage.py today; real agent-invocation
  |     |                           adapters, provider auth, start/monitor/cancel/
  |     |                           timeout/retry/recover — NET NEW, see below;
  |     |                           depends on policy for gating, never bypasses it)
  |           ^
  |           |-- agentrouter-orchestration  (NET NEW multi-agent workflow engine;
  |                                            depends on routing + execution, never
  |                                            the reverse — a workflow plans and
  |                                            dispatches, it does not re-implement
  |                                            scoring or gating)
  |
  |-- agentrouter-storage      (store.py: SQLite decision log, WAL/snapshot)
  |-- agentrouter-security     (bundle.py redaction, plugins.py filesystem hardening)
  |-- agentrouter-skills       (dynamic skill discovery)
  |-- agentrouter-plugins      (plugin install/doctor/uninstall; depends on security)
  |-- agentrouter-graph        (Graphify-equivalent; MISSING today on both sides —
  |                              see Graphify row; this crate starts empty/stubbed
  |                              until a design exists, it is not blocked on by
  |                              anything else in the graph)
  |-- agentrouter-evaluation   (evaluate.py + evaluation/*: gates, adapters, grading)
  |-- agentrouter-annotation   (annotation/*: candidate gen, packs, splits, dedup,
  |                              compare, adjudicate-support — human-review UI/CLI
  |                              only, never generates or adjudicates a label itself)
  |-- agentrouter-api          (server/app.py, contract.py: HTTP surface + the
  |                              committed-contract compatibility gate, via axum)
  |-- agentrouter-mcp          (mcp_server.py: route/classify/explain/list_* tools
  |                              ONLY — this crate must not gain an execution tool
  |                              without the same owner authorization any other
  |                              crate would need)
  |-- agentrouter-cli          (cli.py via clap; depends on everything, nothing
                                 depends on it — the one binary entry point)
```

Dependency rule: arrows point from leaf (`core`) toward `cli`; nothing in
`core`, `classifier`, `registry`, or `policy` depends on `routing`,
`execution`, or `orchestration`. `orchestration` depends on `routing` and
`execution` but neither depends back — this is what keeps "model
recommendation" (`routing`), "execution planning" (the part of `execution`
that decides *how* to run a chosen model/host, before anything runs), "actual
agent execution" (`execution`'s adapters, once they exist), and "multi-agent
orchestration" (`orchestration`) as four separable concerns with their own
acceptance criteria (next section), matching the architecture review's finding
#4/#5. `agentrouter-graph` and `agentrouter-annotation` are siblings with no
inbound edges from the execution/orchestration spine, so neither blocks the
other nor blocks routing being portable on its own.

## Real-execution requirements (net-new scope, not a Python port)

No Python module today starts, monitors, or collects output from a real
agent/model process — see the Execution row in the inventory. The Rust target
must define, before any execution adapter is written in either language:

1. **Execution adapters** — one per supported host/provider, behind a common
   trait (`agentrouter-execution`), each independently authorized (no adapter
   is "on" by default; see non-negotiables above).
2. **Provider authorization** — credential acquisition stays owner-gated and
   credential-gated per `loop/BACKLOG.yaml` P2; no AI session fabricates or
   stores a credential.
3. **Lifecycle**: startup → monitoring → output collection → verification →
   failure handling → cancellation → timeout → resource/budget limits → audit
   logging. Each stage needs its own test (happy path, timeout, cancellation
   mid-flight, malformed output, resource-limit breach) before the adapter is
   considered done — mirroring the EPIC-018 reliability-lab standard already
   applied to the HTTP server (WAL, idempotency, bounded fields).
4. **Remote execution disabled by default**; high-risk/non-auto-approval tasks
   never auto-execute; MCP gains no execution tool as a side effect of adding
   this crate.
5. Acceptance criteria are tracked **separately** for: (a) model
   *recommendation* (already implemented, `agentrouter-routing`), (b)
   execution *planning* (deciding how a chosen recommendation would run,
   without running it — partially implied by `hosts.py` today), (c) actual
   agent *execution* (net new), (d) multi-agent *orchestration* (net new, next
   section) — a milestone cannot claim credit against one by satisfying
   another.

## Multi-agent orchestration architecture (net-new scope)

Also absent from the current codebase (inventory above). Required shape for
`agentrouter-orchestration`:

- **Task decomposition** — split a workflow-shaped request into ordered
  sub-tasks; each sub-task still goes through the existing classification →
  policy → routing pipeline individually, so orchestration never bypasses
  per-task safety gating.
- **Agent/model selection per sub-task** — reuses `agentrouter-routing`,
  never duplicates scoring logic inside the orchestrator.
- **Dependency graph** — sub-tasks form a DAG; a cycle is rejected at plan
  time, not discovered at execution time.
- **Sequential and *safe* parallel execution** — "safe" is load-bearing:
  parallel branches must not write the same file, call the same non-idempotent
  tool key, or share a workspace unless explicitly declared compatible.
- **Isolated workspaces per agent**, **context handoff** between dependent
  sub-tasks, **intermediate verification** before a downstream sub-task
  consumes an upstream result, **failure recovery** (retry vs. abort vs.
  escalate — explicit per sub-task, no silent swallow), **workflow
  cancellation** (must actually stop in-flight sub-tasks, not just stop
  scheduling new ones), **result aggregation**.
- **Explicit measures against**: infinite agent loops (a hard step/time
  budget per workflow, enforced by the orchestrator, not left to the agent to
  self-limit); duplicate execution (idempotency keys per sub-task, same
  pattern as the HTTP server's EPIC-018 fix #4); unbounded costs (a budget
  ceiling checked *before* dispatching each sub-task, not only audited after);
  unauthorized tool calls (every sub-task's tool access is the same
  policy-filtered set a single-task request would get — orchestration grants
  no additional capability); conflicting concurrent file writes (declared
  workspace isolation plus a lock discipline modeled on `plugins.py`'s
  existing per-key `threading.RLock` pattern, ported rather than reinvented).

This section intentionally does not promise a milestone number by itself — it
is realized across R7 (provider execution) and R8 (orchestration) below, each
with its own acceptance criteria, because conflating "can run one agent" with
"can run a safe multi-agent workflow" is exactly the kind of credit-shifting
this plan must not do.

## Module-by-module port plan (existing Python → Rust)

Ordered by the risk/coverage inventory above. Each row names the acceptance
test that must pass before the Rust module can be considered done, and the
rollback criterion if it cannot. This table covers **porting existing,
implemented Python**; the net-new execution/orchestration/graph scope above
is tracked by the milestones (R6–R9), not by this table, because there is no
existing Python behavior to reproduce for it.

| Module (Python) | Port order | Acceptance test | Rollback criterion |
|---|---|---|---|
| `engine.py` | 1 (proof-of-concept) | Same routing decision + explanation trail as Python on the full `loop/PRODUCT_SCENARIOS.yaml` fixture set, byte-for-byte | Any scenario diverges and the cause isn't a deliberate, reviewed behavior change → keep Python engine authoritative |
| `classifier.py` | 2 | Routing test suite (86 cases) reproduced with identical task-type/confidence output | Any classification disagreement on existing fixtures blocks promotion |
| `hosts.py` | 3 | 100%-covered state machine; property-test every transition already covered in Python | Any transition Rust allows that Python rejects (or vice versa) |
| `usage.py` | 4 | UNKNOWN/UNSUPPORTED/AVAILABLE/EXHAUSTED/ERROR state machine, 100% coverage carried over | N/A — no live adapters registered in either language yet |
| `store.py` | 5 | Opens and round-trips an existing Python-created SQLite file (WAL mode, `busy_timeout`, `store.snapshot`) without a data migration step | Any corruption, lock contention regression, or silent snapshot data loss on the existing EPIC-018 regression fixtures |
| `refresh.py` | 6 | Catalog discovery produces the same registry diffs on recorded fixture responses (no live network calls in CI) | Async-model mismatch introduces non-determinism not present in the sync Python version |
| `diagnostics.py` | 7 | `doctor --json` output is field-identical to Python for every `Check` | Any check silently drops or reorders in a way `test_documented_commands.py`-style tests can't catch |
| `bundle.py` | 8 | All 16 credential-format fixtures from the Python redaction corpus still redact; traceback paths still survive unmasked | Any new false-positive/false-negative on the existing fixture corpus — `regex` crate vs Python `re` Unicode/lookaround differences must be resolved before promotion |
| `evaluate.py` + `evaluation/*` | 9 | Bit-identical scores on the frozen 45-case holdout, run against the same fixture inputs; all 7 `QUALITY_GATES.yaml` gates reproduced | Any numeric drift, however small, on the frozen holdout |
| `contract.py` + `server/app.py` | 10 | `api-compatibility` CI job passes against a Rust (`axum`) server serving the same committed `contracts/http/v1/openapi.json` | Any breaking diff the existing semantic-compatibility gate would have caught |
| `plugins.py` | 11 (needs a fresh security review, not a mechanical port) | Full existing plugin test suite (49 cases) plus a **new** Rust-specific security review covering `std::fs` reparse-point/permission-bit semantics on Windows and Linux | Any filesystem security check that was true under Python exception hierarchies but isn't provably true under Rust's `std::fs` error kinds |
| `annotation/*` | 12 | **Revised from the prior "stays Python indefinitely."** Owner has clarified annotation tooling (candidate generation, dataset prep/blinding, annotation file management, progress tracking, export, disagreement/adjudication *support* UI, dataset building, eval integration) must eventually migrate too. Acceptance: every CLI command in `TASK_012_OWNER_ACTIONS.md` reproduced with identical flags/output; frozen-holdout leakage guardrail (`splits.py`) reproduced and independently re-tested, not assumed; blinding behavior (no `template`/`notes` leak into a pack, PR #18's fix) reproduced | Any change to the human-review requirement, the leakage guardrail, or blinding is an automatic rollback regardless of what else passes — this module's bar is "same human process, different implementation," never "faster human process" |
| `mcp_server.py` | 13 | Same 5 tools (`route`, `classify`, `explain`, `list_models`, `list_hosts`), same resource shapes, **zero new tools** unless separately owner-authorized | Any new capability surfaced, intentional or not |
| `cli.py` | 14 (last — depends on every lower layer being ported) | `CLI_SPEC.md` contract tests pass unchanged against the `clap`-based binary | Any flag, exit code, or JSON shape divergence |

Net-new (no Python equivalent to port, acceptance criteria owned by the
milestones below, not this table): real agent-execution adapters
(`agentrouter-execution`'s adapter layer), multi-agent orchestration
(`agentrouter-orchestration`), Graphify-equivalent codebase intelligence
(`agentrouter-graph`).

## Cross-cutting acceptance gates (apply to every module above)

1. The module is not considered ported until its Rust implementation passes
   the **same** test suite (or a 1:1 translated equivalent with identical
   assertions) the Python module passes today — not a newly written,
   looser suite.
2. A module may run in Rust and Python simultaneously behind a feature flag
   during its own port, but the release gates are always evaluated against
   whichever implementation is authoritative for that release — never a mix
   chosen to make a gate pass.
3. Security-sensitive modules (`plugins.py`, `bundle.py`, `store.py`,
   anything in `agentrouter-execution`/`agentrouter-orchestration`) require
   an independent security review of the Rust port, not just the
   implementer's own tests.
4. No threshold in `QUALITY_GATES.yaml` may be lowered, and no mutant may be
   allowlisted, to accommodate a difference in Rust tooling output.
5. Compatibility surfaces preserved without exception: CLI flags/exit codes,
   JSON formats, HTTP contract, MCP tool/resource names, YAML registry
   schemas, SQLite format, eval methodology, security policies, logging
   privacy (no raw prompts/credentials/secrets logged, in either language),
   release thresholds.

## Milestones R0–R13

Each milestone lists requirements, dependencies, deliverables, test cases,
security checks, acceptance criteria, verification evidence expected, and
rollback condition. "Evidence" means a command's actual output, not a claim —
consistent with this repo's standing rule to reproduce before trusting.

| # | Milestone | Depends on | Deliverables | Verification evidence | Rollback condition |
|---|---|---|---|---|---|
| R0 | Architecture & docs (**this PR**) | — | AD-7, this plan, doc annotations | `git diff` reviewed, `pytest -q` shows no regression | N/A — doc-only |
| R1 | Workspace + core types | R0 | **DONE** (`task/rust-r1-workspace`, 2026-10-13) — Cargo workspace skeleton, `agentrouter-core` crate with the `Classification` struct + 6 enums mirroring `agentrouter/schema.py` field-for-field and value-for-value (`approval_level` not `approval`, `"code+tests"` not `CodeTests`, nulls emitted not omitted to match Pydantic's default dump), plus a `print_classification` bin and `tests/test_rust_compat.py` that diffs real Python `model_dump_json()` output against it | `cargo build`/`cargo test --workspace`/`cargo clippy -D warnings`/`cargo fmt --check` all green; `pytest -q` 982 passed/1 skipped (baseline 981/1, +1 new compat test, zero regressions); CI job not yet added (next step) | Workspace doesn't build cross-platform (Windows/Linux, per `AGENTS.md`'s platform invariant) — not yet verified on Windows this session, Linux only |
| R2 | Registries + classification | R1 | **DONE** (`task/rust-r1-workspace`) — `agentrouter-registry` (port of `registry.py`), `agentrouter-classifier` (port of `classifier.py`) | Port-plan rows 1–2 passing — 40-prompt compat test (`tests/test_classifier_rust_compat.py`) and real seed-registry load test both green | Any classification/registry fixture disagreement |
| R3 | Routing + policy + safety | R2 | **DONE** (`task/rust-r1-workspace`) — `agentrouter-policy` (`taxonomy.py` + `controls.py` ports), `agentrouter-routing` (`engine.py` port), `agentrouter-hosts` (`hosts.py` port), `agentrouter-usage` (`usage.py` state machine, minus the CLI/route presentation glue `apply_live_verification`, deferred to R4/R5 alongside the typed `RouteResult` it re-ranks) | Port-plan rows 1, 3–4 passing — 12-scenario routing compat test, 9-case controls compat test (`tests/test_controls_rust_compat.py`), env-controlled hosts compat test (`tests/test_hosts_rust_compat.py`), all byte-identical against Python; full `cargo test --workspace` and `pytest -q` (1050 passed/1 skipped) green | Any scoring/explanation divergence |
| R4 | SQLite + CLI (core commands) | R3 | **PARTIAL** (`task/rust-r1-workspace`) — `agentrouter-storage` DONE: full port of `store.py` (`connect`/`save_decision`/`recent_ids`/`recent_decisions`/`aggregate_stats`/`load_decision`/`snapshot`, same schema, `d_NNNNN` id format, WAL+busy_timeout tuning, in-process write serialization), verified against a real SQLite file both languages read via `tests/test_store_rust_compat.py`. `agentrouter-cli` (the `route`/`classify`/`explain`/`doctor` commands) is **not started** — next step for whoever resumes R4 | Port-plan row 5 (storage) passing; row 7/14 (CLI) still outstanding | Any SQLite round-trip or CLI contract break |
| R5 | HTTP API + TS SDK + MCP | R4 | `agentrouter-api`, `agentrouter-mcp` | `api-compatibility` CI job green against Rust server; TS SDK test suite unchanged and green against it | Any semantic contract diff the existing gate would catch |
| R6 | Provider execution + auth (adapters) | R3, owner credential action | `agentrouter-execution` adapter trait + first real adapter, behind default-off flag | Lifecycle test matrix from **Real-execution requirements** above, all green; security review | Remote execution ever defaults on, or an adapter bypasses policy gating |
| R7 | Multi-agent orchestration | R6 | `agentrouter-orchestration` | Full test matrix from **Multi-agent orchestration architecture** above (loop/duplicate/cost/tool/conflict guards each independently tested) | Any guard in that section fails under adversarial fixture |
| R8 | Graphify + skills + plugins | R4 | `agentrouter-graph` (design + minimal viable query, since Graphify itself is absent — see inventory), `agentrouter-skills`, `agentrouter-plugins` | Port-plan row 11 passing + fresh `std::fs` security review; graph capability has its own test fixtures (no claim of parity with a tool not present on this machine) | Plugin security review finds an unresolved HIGH/CRITICAL |
| R9 | Evaluation + annotation + benchmarking | R4 | `agentrouter-evaluation`, `agentrouter-annotation` | Port-plan row 9 (bit-identical 45-case holdout) and row 12 (annotation CLI parity + leakage guardrail + blinding) both passing | Any holdout numeric drift, or any weakening of the human-review/leakage/blinding guarantees |
| R10 | Security/reliability/perf hardening | R5–R9 | Bandit/pip-audit-equivalent (`cargo-audit`) clean, soak-test equivalent of `reliability/soak.py` | Independent security review across the whole Rust surface; soak run evidence | Any CRITICAL/HIGH finding unresolved |
| R11 | Full Python/Rust parity validation | R1–R10 | Every module in the port-plan table running in Rust, diffed against Python on the full existing regression suite | Side-by-side run, zero behavioral diffs beyond reviewed/accepted ones | Any unreviewed diff |
| R12 | Rust-only runtime validation | R11 | A build/run with the Python package absent entirely | Fresh-machine install + full CLI/HTTP/MCP smoke with no `agentrouter` Python package installed | Any feature silently requires Python |
| R13 | Staging, rollback, release readiness | R12 | Staging deployment plan, rollback drill, update to `RELEASE.md`/`QUALITY_GATES.yaml` evidence requirements for the new implementation | Rollback drill evidence (a real revert exercised, not described); release-readiness review | Any of this plan's non-negotiables violated, or the Release truth gate (`context_band_accuracy`) still failing independent of language |

R6 and R7 are deliberately placed after the interface milestones (R4–R5) and
before the deep-hardening ones (R8–R10): nothing in orchestration or graph
work depends on provider execution existing, but provider execution
legitimately gates orchestration (you cannot safely parallelize agents that
cannot yet run one). R8 (Graphify/skills/plugins) and R9 (evaluation/
annotation) are independent of R6/R7 and of each other — both only need R4 —
so they may run concurrently with R6/R7 without violating any dependency.

## Python retirement criteria

Python (`agentrouter/`) is not removed, deprecated-flagged, or demoted from
release-gate authority until **all** of the following hold simultaneously:

1. Every module in the port-plan table (R2–R9 scope) has a Rust equivalent
   passing its named acceptance test in CI, not just locally.
2. Compatibility tests pass across CLI, HTTP, MCP, and SQLite against the
   Rust implementation, using the *existing* test suites (not rewritten,
   loosened ones).
3. Security review (R10) found 0 unresolved CRITICAL/HIGH across the full
   Rust surface.
4. Evaluation is verified: all seven `QUALITY_GATES.yaml` gates reproduce
   bit-identical on the frozen holdout in Rust.
5. Real-execution workflows are verified wherever real execution is in scope
   (R6 lifecycle matrix green).
6. Multi-agent workflows are verified (R7's adversarial guard matrix green).
7. Graphify-equivalent integration is verified against its own fixtures (R8)
   — not against a historical, possibly-stale baseline.
8. Annotation tooling is migrated (R9) **without** weakening the human-review
   requirement, leakage guardrail, or blinding behavior.
9. Rust CI passes on every supported platform (`AGENTS.md`: Python 3.10–3.13
   equivalents / Windows and Linux support preserved as the Rust target's own
   platform matrix).
10. Staging validated and rollback tested (R13), with evidence, not a plan.
11. The product-architect/security-reviewer review cadence this repo already
    requires (`AGENTS.md`'s engineering loop) has been applied to the
    cutover itself, not only to individual modules.
12. Every release-readiness requirement in `RELEASE.md`/`RELEASE_READINESS.md`
    is satisfied by the Rust implementation — including, independently, the
    annotation-gated `context_band_accuracy` threshold, which this migration
    neither closes nor is blocked by (it's a human-process gate, not a
    language one).

Until all twelve hold, Python remains both the shipping system and the
release-gate authority, exactly as AD-7 states.

## Rollback

Each module is ported on its own branch, merged into the RC only after its
acceptance test passes in CI (not just locally). If a ported module fails its
acceptance test post-merge, the rollback is a revert of that module's merge
commit — the Python implementation it replaced is never deleted until the
**entire** migration (all retirement criteria above) is complete and has run
green in production for a full release cycle. This plan does not authorize
deleting any Python module until that condition is met.

## Explicitly out of scope for this plan

- No Rust code is written as part of producing this plan.
- No Python code is deleted or marked deprecated.
- No release gate, coverage threshold, or mutation threshold is changed.
- No owner-gated action (merge to `main`, tag, publish, deploy, paid
  inference) is taken.
- This plan does not itself close the `context_band_accuracy` gate — see
  `TASK_012_OWNER_ACTIONS.md`, unchanged and unrestated here on purpose.
