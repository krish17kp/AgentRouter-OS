# Python-to-Rust parity inventory

Updated: 2026-11-18 (TASK-082–265). This inventory covers every Python source module under
`agentrouter/` at the current release-candidate head. “Parity” means a
contract-level Python/Rust differential suite exists for the module’s public
behavior; it does not mean the Rust crate has replaced the Python package.
“Partial” identifies a Rust slice with unported behavior or no complete
user-facing entrypoint. “Not ported” means no contract-compatible Rust
implementation is present. The Python implementation remains the shipped
release authority until the full set is complete.

## Inventory

| Python module | Rust counterpart | Status |
|---|---|---|
| `agentrouter/__init__.py` | `agentrouter-core::package_version` | Parity |
| `agentrouter/__main__.py` | `agentrouter-cli::bin::agentrouter` | Parity |
| `agentrouter/annotation/__init__.py` | `agentrouter-evaluation::annotation_api` | Parity |
| `agentrouter/annotation/adjudicate.py` | `agentrouter-evaluation::{annotation_needs_adjudication,resolve_annotation}` | Parity |
| `agentrouter/annotation/candidates.py` | `agentrouter-evaluation::annotation_candidates` | Parity |
| `agentrouter/annotation/cli.py` | `agentrouter-evaluation::annotation_cli` (`agentrouter-evaluate dataset`) | Parity |
| `agentrouter/annotation/compare.py` | `agentrouter-evaluation::annotation_compare` | Parity |
| `agentrouter/annotation/dedup.py` | `agentrouter-evaluation::annotation_dedup` | Parity |
| `agentrouter/annotation/graph_signals.py` | `agentrouter-evaluation::annotation_graph_signals` | Parity |
| `agentrouter/annotation/packs.py` | `agentrouter-evaluation::annotation_packs` | Parity |
| `agentrouter/annotation/schema.py` | `agentrouter-evaluation::annotation_schema` | Parity |
| `agentrouter/annotation/splits.py` | `agentrouter-evaluation::annotation_splits` | Parity |
| `agentrouter/annotation/store.py` | `agentrouter-evaluation::annotation_store` | Parity |
| `agentrouter/bundle.py` | `agentrouter-cli::bundle` | Partial |
| `agentrouter/catalog_ops.py` | `agentrouter-registry::catalog_ops` | Parity |
| `agentrouter/classifier.py` | `agentrouter-classifier` | Parity |
| `agentrouter/cli.py` | `agentrouter-cli::bin::agentrouter` plus command modules | Partial |
| `agentrouter/context_model.py` | `agentrouter-classifier::context_model` | Parity |
| `agentrouter/contract.py` | `agentrouter-cli::contract::{canonicalize,dumps,validate_refs,load_baseline,load_live_contract,diff_contracts_surface,apply_recorded_acceptances,record_breaking_acceptance}` | Partial |
| `agentrouter/controls.py` | `agentrouter-policy::controls` | Parity |
| `agentrouter/dashboard.py` | `agentrouter-cli::dashboard` | Parity |
| `agentrouter/diagnostics.py` | `agentrouter-cli::diagnostics` | Partial |
| `agentrouter/engine.py` | `agentrouter-routing` | Parity |
| `agentrouter/evaluate.py` | `agentrouter-evaluation::legacy_gold::{LegacyGoldError,grade_cases,grade_routing,write_artifacts}` | Parity |
| `agentrouter/evaluation/__init__.py` | `agentrouter-evaluation::evaluation_api` | Parity |
| `agentrouter/evaluation/adapters/__init__.py` | `agentrouter-evaluation::package_markers::ADAPTERS_PUBLIC_EXPORTS` | Parity |
| `agentrouter/evaluation/adapters/agentrouter_gold.py` | `agentrouter-evaluation::AgentRouterGoldAdapter` | Parity |
| `agentrouter/evaluation/adapters/banking77.py` | `agentrouter-evaluation::normalize_banking77_rows` | Partial |
| `agentrouter/evaluation/adapters/clinc150.py` | `agentrouter-evaluation::normalize_clinc150_rows` | Partial |
| `agentrouter/evaluation/adapters/llmrouterbench.py` | `agentrouter-evaluation::llmrouterbench_{describe,full_run_status}` | Parity |
| `agentrouter/evaluation/adapters/longbench_v2.py` | `agentrouter-evaluation::{normalize_longbench_rows,longbench_bucket_for}` | Partial |
| `agentrouter/evaluation/adapters/massive.py` | `agentrouter-evaluation::normalize_massive_rows` | Partial |
| `agentrouter/evaluation/adapters/swebench.py` | `agentrouter-evaluation::normalize_swebench_rows` | Partial |
| `agentrouter/evaluation/adapters/twinrouterbench.py` | `agentrouter-evaluation::twinrouterbench_full_run_status` plus shared adapter base | Parity |
| `agentrouter/evaluation/base.py` | `agentrouter-evaluation::{registry_api::DatasetAdapter,load_adapter_fixture,adapter_availability,sample_adapter_cases,adapter_checksum,describe_adapter}` | Partial |
| `agentrouter/evaluation/cli.py` | `agentrouter-evaluation::bin::agentrouter-evaluate` | Partial |
| `agentrouter/evaluation/comparison.py` | `agentrouter-evaluation::{compare_results,load_result,write_comparison}` | Parity |
| `agentrouter/evaluation/context_bands.py` | `agentrouter-evaluation::context_bands` | Parity |
| `agentrouter/evaluation/evaluators/__init__.py` | `agentrouter-evaluation::evaluators_api` | Parity |
| `agentrouter/evaluation/evaluators/feedback.py` | `agentrouter-evaluation::evaluate_feedback` | Parity |
| `agentrouter/evaluation/evaluators/performance.py` | `agentrouter-evaluation::{evaluate_performance,evaluate_performance_with,evaluate_default_performance,summarize_performance}` | Parity |
| `agentrouter/evaluation/evaluators/platform.py` | `agentrouter-evaluation::{evaluate_platform,evaluators_api::runtime_cli_surface}` | Parity |
| `agentrouter/evaluation/evaluators/provider.py` | `agentrouter-evaluation::{evaluate_provider,evaluate_provider_default}` | Parity |
| `agentrouter/evaluation/evaluators/routing.py` | `agentrouter-evaluation::{evaluate_routing,evaluate_routing_with}` | Parity |
| `agentrouter/evaluation/evaluators/safety.py` | `agentrouter-evaluation::{evaluate_safety,evaluate_safety_with}` | Parity |
| `agentrouter/evaluation/grading.py` | `agentrouter-evaluation::{grade_classification,runner::{run_default_grade,run_default_grade_with,run_all_dimensions}}` | Parity |
| `agentrouter/evaluation/metrics.py` | `agentrouter-evaluation::classification_metrics` | Parity |
| `agentrouter/evaluation/provenance.py` | `agentrouter-evaluation::{dataset_quality,environment_snapshot}` | Parity |
| `agentrouter/evaluation/registry.py` | `agentrouter-evaluation::registry_api::{adapter,available_adapter_factories,dataset_spec,collect,profile}` | Partial |
| `agentrouter/evaluation/reports.py` | `agentrouter-evaluation::{render_markdown, write_reports}` | Parity |
| `agentrouter/evaluation/runner.py` | `agentrouter-evaluation::runner::{run_classification,run_all_dimensions,run_registered,runtime_environment}` | Parity |
| `agentrouter/evaluation/sampling.py` | `agentrouter-evaluation::deterministic_sample` | Parity |
| `agentrouter/evaluation/schema.py` | `agentrouter-evaluation::{EvaluationCase,ExpectedClassification,Provenance,normalized_hash}` | Parity |
| `agentrouter/harness.py` | `agentrouter-cli::harness` | Parity |
| `agentrouter/hosts.py` | `agentrouter-hosts` | Parity |
| `agentrouter/learning.py` | `agentrouter-learning::learned_weights` | Parity |
| `agentrouter/mcp_server.py` | `agentrouter-mcp::{Server,run_stdio}` | Partial |
| `agentrouter/observability.py` | `agentrouter-observability` (task-local/synchronous request context, redaction, route/event/error records, OTel spans) | Parity |
| `agentrouter/openai_adapter.py` | `agentrouter-cli::openai` | Parity |
| `agentrouter/plugins.py` | `agentrouter-cli::plugins` (inventory, portable paths, no-follow state, list/status/doctor/plan, safe install/uninstall, forced unmanaged replacement, identity-checked journal recovery) | Partial |
| `agentrouter/prompts.py` | `agentrouter-cli::generate_prompt` | Parity |
| `agentrouter/refresh.py` | `agentrouter-cli::providers` + `agentrouter-registry::refresh` | Parity |
| `agentrouter/registry.py` | `agentrouter-registry` | Parity |
| `agentrouter/reliability/__init__.py` | `agentrouter-reliability::PYTHON_PACKAGE_EXPORTS` | Parity |
| `agentrouter/reliability/harness.py` | `agentrouter-reliability::{LoadSpec,LoadOutcome,run_load,serve_app,serve_router,RunningApp}` | Partial |
| `agentrouter/reliability/soak.py` | `agentrouter-reliability::{Sample,SoakResult,soak,soak_app}` and `agentrouter reliability soak` | Partial |
| `agentrouter/safety.py` | `agentrouter-policy` | Parity |
| `agentrouter/schema.py` | `agentrouter-core + agentrouter-registry` | Parity |
| `agentrouter/sdk.py` | `agentrouter-cli::sdk` | Partial |
| `agentrouter/server/__init__.py` | `agentrouter-evaluation::package_markers::SERVER_PUBLIC_EXPORTS` | Parity |
| `agentrouter/server/app.py` | `agentrouter-api::server` + `agentrouter-api-server` | Parity |
| `agentrouter/server/limits.py` | `agentrouter-limits` (re-exported as `agentrouter_cli::limits`) | Parity |
| `agentrouter/server/schemas.py` | `agentrouter-api::{schemas,responses}` | Parity |
| `agentrouter/server/service.py` | `agentrouter-api::service` | Parity |
| `agentrouter/store.py` | `agentrouter-storage` | Parity |
| `agentrouter/taxonomy.py` | `agentrouter-policy::taxonomy` | Parity |
| `agentrouter/usage.py` | `agentrouter-usage::{check_usage,apply_live_verification}` | Parity |

## Release interpretation

- TASK-218 adds bounded Rust `contract check --live URL` verification, explicit
  `--baseline PATH` selection, and manifest-recorded acceptance handling. TASK-
  219 aligns Rust export with the explicit `--accept-breaking --reason TEXT`
  workflow and preserves acceptance history. The Rust surface verifies a
  running service against the committed baseline, but the Python framework
  remains authoritative for schema generation and hosted release approval, so
  this module remains Partial.

- TASK-176 adds a direct entrypoint differential: `python -m agentrouter --help`
  and the Rust unified binary both expose the public route, registry, providers,
  and doctor commands and return successful help/version responses. The one-line
  Python module is now contract-covered as Parity; broader CLI behavior remains
  tracked by the `agentrouter/cli.py` row.

- TASK-140 adds direct nine-endpoint wire-contract comparisons for the Python and
  Rust SDKs, including API-key variants and structured API errors. TASK-141 adds
  a public Rust transport trait, timeout propagation, idempotent close, stable
  error categories, and all-nine-endpoint comparison against Python's injected
  `httpx.MockTransport`. TASK-147 explicitly bounds native `ureq` TCP connection
  setup from the client timeout, alongside its whole-request deadline. The SDK
  remains Partial because the `ureq` global deadline differs from HTTPX's
  per-operation timeout model and some native I/O failures do not preserve their
  read/write phase.
- TASK-209 makes the TypeScript live parity helper initialize Rust homes with the
  Rust `init_cli` binary. With `AGENTROUTER_REQUIRE_LIVE=1`, all 18 TypeScript
  tests pass against the Rust loopback server with zero skips; the remaining SDK
  row is partial only for broader lifecycle/native transport parity.
- TASK-225 aligns native Rust SDK truncation handling with HTTPX by classifying
  a declared-length body that ends early as `RemoteProtocolError`; generic
  native phase-specific I/O and lifecycle parity remain Partial.
- TASK-142 expands the evaluator facade differential from model identity fields
  to every normalized `ModelEntry` JSON field and compares the Rust export list
  directly with Python's `__all__`. TASK-160 adds success-only cached loading,
  retry semantics, no-argument defaults, and explicit/injected facade aliases.
- TASK-143 connects the full Rust evaluation CLI to the installed `agentrouter`
  binary's actual command/group manifest. A missing sibling binary is an error
  for `run --all`; the report no longer substitutes a hardcoded two-entry
  surface. Other evaluator defaults and runtime orchestration remain Partial.
- TASK-220 makes the Rust evaluation and annotation CLIs plus the diagnostics
  contract path relocatable with `AGENTROUTER_PROJECT_ROOT` and
  current-working-directory repository discovery before the build-time
  fallback. External dataset loading and full evaluator orchestration remain
  Partial.
- TASK-221 sets Unix Rust diagnostic-bundle artifacts to private `0600` mode on
  the opened capability-bounded handle. TASK-259 additionally aligns JSON
  artifacts with Python's ASCII escaping, including surrogate pairs for
  non-BMP characters. Bundle metadata/runtime parity remains Partial.
- TASK-262 aligns the shared adapter `prepare(limit)` contract: both
  implementations validate the complete real source and then report the
  deterministic seed-0 smoke subset for bounded prepares. External loader and
  cache lifecycle parity remain Partial.
- TASK-144 tightens the existing OpenAI adapter parity: both implementations
  reject all non-2xx responses regardless of whether the concrete transport or
  an injected fixture produced the status. Redirects remain disabled.
- TASK-145 adds full `EvaluationCase` differentials for CLINC150's ordered
  intent map, `oos` handling, and real-row normalization/deduplication. The
  module remains Partial because its external Hugging Face loading contract is
  Python-only.
- TASK-149 adds recursive JSON redaction comparisons for nested objects and
  arrays, including authorization headers, provider tokens, generic API-key
  fields, and ordinary paths.
- TASK-152 shares Rust redaction across API and CLI, matches Python route
  decision metadata, and emits opt-in JSON route records correlated through
  SHA-256 request-ID digests, with strict redaction of nested metadata values
  and keys. TASK-168 completes task-local/synchronous request context, opt-in
  logging, generic events, bounded API-error records, active OTel spans, and
  single-emission server error paths. HTTP service errors use bounded,
  message-only evidence when no rendered traceback is available.
- TASK-150 preserves Pydantic's arbitrary-precision `ModelSummary.context_window`
  response value in Rust, including values outside signed 64-bit range, and
  differentially checks accepted and rejected coercions. The schema module stays
  Partial until every public model and FastAPI behavior is covered.
- The Rust workspace has no `TODO`, `todo!()`, or `unimplemented!()` markers in
  shipped Rust source, but that does not make unported Python behavior complete.
- The Python modules marked **Partial** and **Not ported** remain production
  responsibilities. The CLI, HTTP, MCP, plugin/skill, evaluation/annotation,
  diagnostic-bundle, and reliability surfaces still have Rust contract gaps.
- Rust contract tooling currently matches Python's recursive OpenAPI
  canonicalization rules for sorted object keys, order-insensitive schema/tag
  lists, schema branches, and parameters, and emits two-space Unicode JSON with
  a final newline. It also checks local `$ref` targets, reports external,
  missing, and cyclic references, and applies the same 200,000-node budget.
  The baseline loader reads the committed artifact, preserves Python's missing,
  malformed, non-OpenAPI, and untrusted-reference failure states, and applies
  the same traversal limit. Differential fixtures cover the live document,
  invalid references, and baseline failures. A separately named surface-diff
  probe covers versions, server URLs, paths/methods, selected operation
  metadata, operation authentication requirements and scheme definitions,
  parameter add/remove/requiredness changes, request-body requiredness,
  request and response media-type additions/removals,
  response status additions/removals/refinements, and summary/description
  changes, plus inline request/response schema type, field-presence/requiredness,
  array-item, enum/const, numeric/size bound, pattern, format, default, and
  `additionalProperties` changes, and matching operation-parameter schemas.
  Schema `$ref` traversal is bounded and handles local aliases, nested refs
  (including union branches), missing/external references, and recursive
  schemas with Python-compatible results. Nullable wrappers and
  `type: [T, null]` are classified separately; `anyOf`/`oneOf` branch counts,
  `allOf` conjunction direction, payload changes, and branch ordering have
  Python differential coverage. It remains a partial surface probe, not the
  full semantic compatibility checker or a release gate.
  Rust export now canonicalizes an input document, records product/API/source
  provenance and operation count, and safely writes both artifacts with pinned
  directory handles and atomic replacement. Symlink and hard-link targets are
  refused. The full semantic compatibility checker and the unified CLI command
  remain Python-only.
- The Rust MCP process implements the five Python tools, current stateless
  `server/discover` flow, per-request version validation and server identity,
  plus the legacy `initialize` path. Official Python SDK 2.x differentials
  cover modern discovery and legacy negotiation, tool schemas/results, and
  unknown tools; Rust CLI stdio tests cover both protocol eras. The optional
  Python extra keeps SDK 1.x on Python 3.10 and uses SDK 2.x on Python 3.11+.
  The unified CLI dispatches `mcp` to the Rust stdio server. The module remains
  Partial while broader MCP lifecycle, transport, and error behavior is audited.
- The unified CLI now exposes read-only `plan` plus safety-gated `execute` for configured provider
  argv, available local host commands, and OpenAI text requests. It recomputes
  the recorded classification gate, refuses high-risk and tampered decisions,
  and runs commands without a shell. The OpenAI adapter request and response
  contract is differentially checked against Python over 20 offline fixtures;
  credential privacy, bounded reads, validation and provider errors, refusal,
  malformed/oversized responses, and redirect refusal are covered. Live key
  validation remains a release check, while broader cross-platform command
  behavior keeps the CLI module Partial.
- Rust provider refresh converts and filters OpenRouter/OpenAI catalogs,
  performs fixed-endpoint HTTPS retrieval with header-only keys, reports
  report-only deprecations, and atomically writes generated catalogs without
  touching the manual registry. Offline model and payload conversion, bounded
  transport, and generated-file behavior have Rust tests. Full exception and
  CLI-output parity plus live OpenAI visibility validation remain outstanding,
  so the module is Partial.
- Rust reliability summarizes load/soak results, drives bounded HTTP load, and
  owns a loopback API lifecycle through `serve_app`/`serve_router` and
  `RunningApp`. `agentrouter reliability soak` initializes a local home, runs
  the Rust API, and writes the soak report. Truncated declared-length response
  bodies now classify as `RemoteProtocolError`, matching HTTPX. `ureq` does
  not retain read/write direction for every generic I/O error, and Python
  package-level invocation now delegates through `python -m
  agentrouter.reliability`, but native transport phase taxonomy and broader
  module/runtime parity remain Partial. See
  [`RUST_RELIABILITY.md`](RUST_RELIABILITY.md) for scope.
- The reliability package initializer's five re-exported names now have an
  exact Python/Rust inventory check. Behavior of `run_load` and `serve_app` is
  still tracked by the harness row, so export parity does not imply full
  harness parity.
- Rust quota status normalization and one-step exhausted-model reranking are
  compared with Python for all declared states, Unicode sanitization, invalid
  states, missing recommendations, ranking output, timeout, and typed adapter
  errors. Rust adapters can return `LiveCheckError` with the source exception
  class name, matching Python's safe error detail without exposing provider
  messages. Panics remain isolated as `panic`. No real provider quota adapters
  are registered in either implementation, so both report `unsupported` for
  live checks until a provider adapter is deliberately added.
- The historical classifier and routing-gold evaluator, report rendering, and
  artifact writing are implemented in Rust and differentially checked against
  the full checked-in gold sets. Gold loading preserves Python's error
  categories and messages for missing, malformed-shape, and duplicate-ID
  inputs; artifact JSON matches Python's ASCII escaping byte-for-byte. See
  [`RUST_LEGACY_GOLD.md`](RUST_LEGACY_GOLD.md).
- Rust `Classification` rejects unknown fields and has round-trip and rejection
  checks against Pydantic. Its `confidence` field now matches Pydantic number,
  numeric-string, and boolean coercion with the 0–1 bound; `needs_clarification`
  matches boolean, 0/1 numeric, and recognized string forms. `context_tokens`
  now preserves Python's signed arbitrary-precision integer values and Pydantic
  numeric/string/boolean coercions. Classifier estimates and routing capacity
  checks also preserve the exact integer rather than truncating to `u32`.
  Rust `ModelEntry.context_window`, `max_input_tokens`, and
  `max_output_tokens` likewise preserve arbitrary-precision positive integers
  across YAML/JSON registry loading, OpenRouter refresh, evaluation, route
  scoring, and display. Differential cases exercise values beyond `u64` and
  Python's rounded 2x/16x context-fit boundaries. The `agentrouter/schema.py`
  module remains Partial pending full-module differential coverage for all
  public types and behavior.
  Annotation manifest schema versions and count maps
  now preserve Python-compatible arbitrary-precision integers exactly in
  schema validation and JSON storage. TASK-166 closes the full annotation schema
  contract: public deserialization always runs semantic validators; nested labels
  fail closed; constants, required/default/null and extra-field policies,
  agreement edges, and extended datetime boundaries are differential-tested.
- Rust registry dates now normalize the Pydantic-accepted YAML date, midnight
  datetime, and epoch-second/millisecond forms to the same ISO date in JSON;
  differential cases cover all three optional date fields and reject
  non-midnight timestamps and invalid offsets. Registry integer, float, and
  boolean fields also accept and reject the same scalar forms as Pydantic,
  including decimal integer strings, integral floats, booleans-as-numbers,
  numeric separators, and exact boolean tokens. Differential tests cover
  accepted and rejected forms. Its custom JSON scalar visitor handles
  `serde_json/arbitrary_precision` number tokens, and YAML rejects the private
  serde_json marker representation. Rust `Ability` now enforces its 0–10
  integer bounds during direct deserialization, with Python/Rust cases for
  accepted coercions, invalid bounds, unknown fields, and missing fields.
  `ExecutionTarget` and `Provider` now also have direct Python/Rust JSON
  roundtrip probes for defaults, boolean coercion, enum selection, required
  fields, unknown fields, and invalid nested values. TASK-131 directly checks
  every one of the twelve public schema enums: all 45 declared values serialize
  identically and representative invalid strings, nulls, and numbers are
  rejected by both runtimes. TASK-132 now directly checks `ModelEntry` defaults,
  all required fields, coercions, numeric constraints, dates, nested execution
  targets, unknown fields, normalized serialization, and its `vendor`, `key`,
  `vendor_key`, and `name` properties. Python also rejects non-finite price and
  confidence metadata at validation, matching Rust's safety constraints.
  TASK-133 closes the public schema inventory: direct differentials now cover
  every required field and omitted defaults for `Ability`, `ExecutionTarget`,
  `Provider`, `ModelEntry`, and `Classification`; populated Classification
  optionals and its alternative task enum; all twelve enums; scalar coercions,
  invalid values, bounds, unknown-field rejection, nested values, normalized
  serialization, model-derived properties, and the `ModelEntry` vendor
  validator. The Python/Rust probes and the full Python regression pass, so
  `agentrouter/schema.py` meets the module parity bar.
- Context-band model inference is ported but remains disabled in the default
  classifier. The frozen evaluation gate still controls whether learned routing
  can be enabled.
- The optional repository graph signal matches Python's four-entry LRU cache,
  cached fallbacks, malformed-shape behavior, and contextual Unicode lowercase
  for graph edge identifiers.
- Context-band annotation comparison matches rules, learned and hybrid
  prediction reports, including macro-F1, per-band recall, deterministic
  CPython-seeded bootstrap confidence intervals, ECE, abstention and fallback
  counts. It only measures; it does not change classifier thresholds or gates.
- Evaluation JSON, scorecard, Markdown, failure/holdout CSV, confusion CSV, and
  output file ordering all have a Python/Rust differential fixture.
- TASK-237 aligns evaluation CLI status with Python's path-based fixture
  availability: an empty-but-present fixture remains `fixture: true` rather
  than being inferred missing from a zero record count.
- TASK-238 aligns evaluation CLI `prepare` with Python for unknown dataset
  names: the adapter is reported as unavailable and the single-dataset probe
  exits 1 instead of surfacing a registry lookup error.
- TASK-240 aligns evaluation CLI invalid `validate-dataset` errors with
  Python's `Invalid dataset:` prefix and exit code 3.
- TASK-239 aligns guarded execution runtime failures with Python's exit code 1
  for missing commands and provider/host transport failures.
- TASK-241 aligns direct Rust `route` with Python classifier overrides,
  preference flags, no-log behavior, and preview/availability compatibility
  options. Broader CLI and runtime lifecycle parity remains partial.
- TASK-243 aligns direct Rust `route` invalid-option failures with Python's
  exit-2 `Error:` contract; broader CLI and runtime lifecycle parity remains
  partial.
- TASK-245 adds successful unified subgroup help for core `models`, `hosts`,
  `providers`, and `registry` inspection commands; full CLI behavior remains
  partial.
- Classification-only grading and gate calculation have differential coverage.
  Rust also supports bounded `measure_all` scoring for caller-supplied cases,
  seed models, and command manifests; automatic runtime discovery remains
  partial.
- The safety evaluator now classifies and gates cases in Rust with differential
  coverage. Feedback, provider, routing, platform, and performance have Rust
  scoring and caller-supplied/default input paths. Performance summary values
  match exactly for fixed samples; measured latency values are machine-specific
  by contract. Runtime-wide evaluator orchestration remains partial.
- The Rust routing evaluator preserves Python's insertion-order dictionary
  behavior for duplicate model keys: the last supplied entry is used to check
  routing constraints, even though routing may return that shared key from an
  earlier entry. A differential fixture covers this edge case.
- Routing and safety evaluators accept the same injected-classifier seam as
  Python. Differential probes supply task-keyed classifications and verify the
  complete score and failure reports while retaining their existing default
  classifier behavior.
- Provider metadata scoring supports caller-supplied model records and a
  no-argument path that loads and validates the packaged seed registry, matching
  Python's default evaluator behavior.
- The feedback/storage evaluator now uses the Rust SQLite store in a unique
  temporary home and compares the same decision, feedback, and aggregation
  checks. The platform evaluator matches scoring for a caller-supplied CLI
  command/group manifest; runtime Typer command discovery remains Python-only.
- The Rust limits module matches Python's client-key precedence, fixed-window
  rate checks, retry-after values, environment configuration, response TTL and
  media type, bounded retention, successful-response caching, failure/non-2xx
  recomputation, and per-key single-flight behavior. Python's `asyncio.Lock`
  workflow is compared to Rust's synchronous keyed-computation API at the
  observable response/call-count boundary; distinct keys remain independent.
  Rust Axum applies rate limiting and idempotent replay in its HTTP middleware.
- Rust catalog operations include provenance reads, freshness summaries,
  sorted generated-catalog listing and deprecation reports, plus rollback and
  restore with raw-byte preservation, exclusive backup creation, linked-file
  refusal and no-clobber restoration. Typed Rust failures expose Python's
  `CatalogError`, `ValueError`, `FileExistsError`, and `OSError` categories.
  Differential tests cover malformed YAML and UTF-8, mapping validation,
  Python date formats and summary sanitization, non-directory listings,
  backup rotation, restore collisions, and linked-file refusal. Python now
  applies the same no-follow and exclusive-write safeguards.
- The Rust dashboard page renderer matches Python's complete HTML output over
  empty, escaped, truncated, and aggregate-bearing cases. Its loopback server
  is checked against Python's rendered SQLite output and refuses write methods
  without changing the decision log.
- Python and Rust doctor database checks inspect existing files read-only and
  report matching actionable `OperationalError` or `DatabaseError` categories
  for empty and corrupt databases. Rust now aggregates its safe plugin
  destination findings into the same blocked/attention summary as Python, and
  reports its built-in REST API as available. Diagnostics as a whole remain
  Partial because native runtime/version details differ from Python's and some
  environment check summaries are not fully equivalent.
- The complete `store.py` public data contract is differentially checked over
  a shared SQLite database: identity precedence and OS-account fallback,
  concurrent first-use migration and decision writes, Python/Rust save and
  read directions, all summaries and tier-aware statistics, feedback, online
  snapshots in both directions, numeric decision-ID forms, signed/unsigned
  64-bit integer boundaries, and fail-closed malformed/non-object payload
  handling. Python rejects out-of-range integers and non-standard NaN/infinity
  values before persistence, matching Rust's JSON number domain.
- The Rust SDK client covers Python endpoint paths, payload cleanup, an
  optional API-key header, timeout configuration and structured HTTP errors.
  The local HTTP server and end-to-end client/server contract remain
  Python-only; redirects are disabled so a key cannot be forwarded elsewhere.
- TASK-169 closes the HTTP application lifecycle row after direct process
  differentials for auth/rate/CORS short circuits, request-ID guarantees,
  malformed-registry errors, idempotency non-caching, and executable default
  home resolution. The Rust API crate now ports classify, route, feedback and dry-run request
  bounds, typed response models, and passthrough envelopes that preserve
  engine-owned fields. Differential checks cover supported Pydantic boolean and
  integer coercions and field-level 422 responses, including unbounded signed
  Classification context-token values; some docs behavior, other unbounded
  integer fields, and parts of the server lifecycle remain unported, so the
  HTTP schema module is Partial. The TypeScript SDK exercises all
  manifest operations against the Rust process in the cross-platform CI job.
- Rust API service functions now match Python model and host listings,
  classification, no-log and persisted routing, decision lookup, nullable-note
  feedback, and dry-run previews using committed local registries and SQLite.
Rust now serves those functions over Axum, and the TypeScript SDK drives every
manifest operation against that process. FastAPI middleware/observability
edge cases remain open, so service parity is Partial.
- Performance scoring and classification/routing timing now run in Rust for
  caller-supplied models and tasks. Seed loading and injected classifier
  behavior remain Python-side; latency values are machine-dependent.
- Baseline/current comparison scoring, UTF-8 result loading, and Markdown/CSV
  artifact generation match Python.
- The AgentRouter gold adapter now matches Python metadata, availability, description, all 165 records, checksums, and deterministic sampling; the full behavior is differentially tested, including Unicode/default handling.
- Shared fixture-mode evaluation adapter behavior now matches six fixture-backed adapters for metadata, availability, description, JSONL record loading/checksums, deterministic sampling, and explicit skipped-external behavior. Rust also provides an explicitly opt-in bounded Hugging Face rows-API loader and adapter-specific real-data mappings for CLINC150, Banking77, MASSIVE, LongBench v2, and SWE-bench metadata preparation. LLMRouterBench/TwinRouterBench external sources, Docker/model full runs, and annotation workflows remain Python-only.
- Evaluation provenance now matches Python for dataset-quality/leakage aggregation and the complete four-field runtime environment snapshot.
- The Rust plugin module ports the bundled manifest, portable path trust
  boundary, no-follow ownership-state reads, read-only list/doctor and dry-run
  planning, safe no-force installation, ownership-checked uninstall, forced
  replacement of unmanaged files, and transaction recovery. Rust-created
  ownership state and journals are Python-compatible. Differential checks cover
  owned and unmanaged files, backup collisions, concurrent edits, pre-identity
  and post-identity crash boundaries, rollback, malformed or forged journals,
  verified backup restoration, historical paths, hard-link refusal, and
  identity-checked empty-directory cleanup. TASK-114 adds journaled
  managed-payload upgrades and preserves prior backup metadata. Full CLI parity
  remains incomplete; local full-suite verification passes while
  cross-platform hosted validation is pending.
  Windows parity uses the CPython-compatible file-ID query where supported and
  fails closed for 128-bit identities the current state schema cannot encode.
- Routing evaluation now scores caller-supplied model catalogs against gold
  constraints or the declared distinct-fallback proxy. Loading seed models and
  custom classifier injection remain Python-only.
- This table is a release checklist, not a replacement for CI evidence. Add a
  differential suite before moving any row to **Parity**.
