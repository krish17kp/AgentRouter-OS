# Python-to-Rust parity inventory

Updated: 2026-11-14 (TASK-082–127). This inventory covers every Python source module under
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
| `agentrouter/__main__.py` | `agentrouter-cli::bin::agentrouter` | Partial |
| `agentrouter/annotation/__init__.py` | `agentrouter-evaluation::annotation_api` | Parity |
| `agentrouter/annotation/adjudicate.py` | `agentrouter-evaluation::{annotation_needs_adjudication,resolve_annotation}` | Parity |
| `agentrouter/annotation/candidates.py` | `agentrouter-evaluation::annotation_candidates` | Parity |
| `agentrouter/annotation/cli.py` | `agentrouter-evaluation::annotation_cli` (`agentrouter-evaluate dataset`) | Partial |
| `agentrouter/annotation/compare.py` | `agentrouter-evaluation::annotation_compare` | Parity |
| `agentrouter/annotation/dedup.py` | `agentrouter-evaluation::annotation_dedup` | Parity |
| `agentrouter/annotation/graph_signals.py` | `agentrouter-evaluation::annotation_graph_signals` | Parity |
| `agentrouter/annotation/packs.py` | `agentrouter-evaluation::annotation_packs` | Parity |
| `agentrouter/annotation/schema.py` | `agentrouter-evaluation::annotation_schema` | Partial |
| `agentrouter/annotation/splits.py` | `agentrouter-evaluation::annotation_splits` | Parity |
| `agentrouter/annotation/store.py` | `agentrouter-evaluation::annotation_store` | Parity |
| `agentrouter/bundle.py` | `agentrouter-cli::bundle` | Partial |
| `agentrouter/catalog_ops.py` | `agentrouter-registry::catalog_ops` | Parity |
| `agentrouter/classifier.py` | `agentrouter-classifier` | Parity |
| `agentrouter/cli.py` | `agentrouter-cli::bin::agentrouter` plus command modules | Partial |
| `agentrouter/context_model.py` | `agentrouter-classifier::context_model` | Parity |
| `agentrouter/contract.py` | `agentrouter-cli::contract::{canonicalize,dumps,validate_refs,load_baseline,diff_contracts_surface}` | Partial |
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
| `agentrouter/evaluation/base.py` | `agentrouter-evaluation::{load_adapter_fixture,adapter_availability,sample_adapter_cases,adapter_checksum,describe_adapter}` | Partial |
| `agentrouter/evaluation/cli.py` | `agentrouter-evaluation::bin::agentrouter-evaluate` | Partial |
| `agentrouter/evaluation/comparison.py` | `agentrouter-evaluation::{compare_results,load_result,write_comparison}` | Parity |
| `agentrouter/evaluation/context_bands.py` | `agentrouter-evaluation::context_bands` | Parity |
| `agentrouter/evaluation/evaluators/__init__.py` | `agentrouter-evaluation::evaluators_api` | Partial |
| `agentrouter/evaluation/evaluators/feedback.py` | `agentrouter-evaluation::evaluate_feedback` | Parity |
| `agentrouter/evaluation/evaluators/performance.py` | `agentrouter-evaluation::{evaluate_performance,evaluate_performance_with,evaluate_default_performance,summarize_performance}` | Parity |
| `agentrouter/evaluation/evaluators/platform.py` | `agentrouter-evaluation::evaluate_platform` | Partial |
| `agentrouter/evaluation/evaluators/provider.py` | `agentrouter-evaluation::{evaluate_provider,evaluate_provider_default}` | Parity |
| `agentrouter/evaluation/evaluators/routing.py` | `agentrouter-evaluation::{evaluate_routing,evaluate_routing_with}` | Parity |
| `agentrouter/evaluation/evaluators/safety.py` | `agentrouter-evaluation::{evaluate_safety,evaluate_safety_with}` | Parity |
| `agentrouter/evaluation/grading.py` | `agentrouter-evaluation::{grade_classification,runner::run_all_dimensions}` | Partial |
| `agentrouter/evaluation/metrics.py` | `agentrouter-evaluation::classification_metrics` | Parity |
| `agentrouter/evaluation/provenance.py` | `agentrouter-evaluation::{dataset_quality,environment_snapshot}` | Parity |
| `agentrouter/evaluation/registry.py` | `agentrouter-evaluation::registry_api::{dataset_spec,collect,profile}` | Partial |
| `agentrouter/evaluation/reports.py` | `agentrouter-evaluation::{render_markdown, write_reports}` | Parity |
| `agentrouter/evaluation/runner.py` | `agentrouter-evaluation::runner::{run_classification,run_all_dimensions,run_registered}` | Partial |
| `agentrouter/evaluation/sampling.py` | `agentrouter-evaluation::deterministic_sample` | Parity |
| `agentrouter/evaluation/schema.py` | `agentrouter-evaluation::{EvaluationCase,ExpectedClassification,Provenance,normalized_hash}` | Parity |
| `agentrouter/harness.py` | `agentrouter-cli::harness` | Parity |
| `agentrouter/hosts.py` | `agentrouter-hosts` | Parity |
| `agentrouter/learning.py` | `agentrouter-learning::learned_weights` | Parity |
| `agentrouter/mcp_server.py` | `agentrouter-mcp::{Server,run_stdio}` | Partial |
| `agentrouter/observability.py` | `agentrouter-cli::observability` | Partial |
| `agentrouter/openai_adapter.py` | `agentrouter-cli::openai` | Parity |
| `agentrouter/plugins.py` | `agentrouter-cli::plugins` (inventory, portable paths, no-follow state, list/status/doctor/plan, safe install/uninstall, forced unmanaged replacement, identity-checked journal recovery) | Partial |
| `agentrouter/prompts.py` | `agentrouter-cli::generate_prompt` | Parity |
| `agentrouter/refresh.py` | `agentrouter-registry::refresh` | Partial |
| `agentrouter/registry.py` | `agentrouter-registry` | Parity |
| `agentrouter/reliability/__init__.py` | `agentrouter-reliability` | Partial |
| `agentrouter/reliability/harness.py` | `agentrouter-reliability::{LoadSpec,LoadOutcome,run_load}` | Partial |
| `agentrouter/reliability/soak.py` | `agentrouter-reliability::{Sample,SoakResult,soak}` | Partial |
| `agentrouter/safety.py` | `agentrouter-policy` | Parity |
| `agentrouter/schema.py` | `agentrouter-core + agentrouter-registry` | Partial |
| `agentrouter/sdk.py` | `agentrouter-cli::sdk` | Partial |
| `agentrouter/server/__init__.py` | `agentrouter-evaluation::package_markers::SERVER_PUBLIC_EXPORTS` | Parity |
| `agentrouter/server/app.py` | `agentrouter-api::server` + `agentrouter-api-server` | Partial |
| `agentrouter/server/limits.py` | `agentrouter-limits` (re-exported as `agentrouter_cli::limits`) | Partial |
| `agentrouter/server/schemas.py` | `agentrouter-api::{schemas,responses}` | Partial |
| `agentrouter/server/service.py` | `agentrouter-api::service` | Partial |
| `agentrouter/store.py` | `agentrouter-storage` | Parity |
| `agentrouter/taxonomy.py` | `agentrouter-policy::taxonomy` | Parity |
| `agentrouter/usage.py` | `agentrouter-usage::{check_usage,apply_live_verification}` | Parity |

## Release interpretation

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
- The Rust MCP process implements the five Python tools and stdio lifecycle;
  protocol/tool and result differentials cover all five. The unified CLI now
  runs this stdio server in-process with the selected AgentRouter home. Broader
  cross-version lifecycle/error and command-line behavior remain under
  compatibility review, so the module is Partial.
- The unified CLI now exposes safety-gated `execute` for configured provider
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
- Rust reliability currently summarizes load/soak results and drives bounded
  HTTP load against an already-running server. It does not yet own server
  startup/shutdown, arbitrary Python request factories, or complete transport
  exception naming; those Python harness and CLI contracts remain Partial. See
  [`RUST_RELIABILITY.md`](RUST_RELIABILITY.md) for the supported surface.
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
  schema validation and JSON storage. Raw timestamp differentials now exercise
  Pydantic's datetime parsing directly, including reduced-precision times with
  `Z` and numeric offsets. The annotation schema module remains Partial while
  broader timestamp grammar coverage is unfinished.
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
  `schema.py` remains Partial because there is not yet a full module-level
  differential probe for every public model, enum, default, validator, and
  derived property; the individual parity slices above do not close that
  inventory.
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
- The Rust limits module matches fixed-window rate checks, retry-after values,
  response TTL and media type, bounded response-body retention, and per-key
  single-flight behavior. Rust Axum applies the limits in its HTTP middleware.
  Python exposes asyncio flight-lock methods while Rust provides a synchronous
  keyed computation seam, so the public module remains Partial.
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
- The Rust API crate now ports classify, route, feedback and dry-run request
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
- Shared fixture-mode evaluation adapter behavior now matches six fixture-backed adapters for metadata, availability, description, JSONL record loading/checksums, deterministic sampling, and explicit skipped-external behavior. Real dataset downloads, preparation, and adapter-specific real-data mappings remain Python-only.
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
