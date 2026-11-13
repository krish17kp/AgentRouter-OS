# Python-to-Rust parity inventory

Updated: 2026-11-13. This inventory covers every Python source module under
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
| `agentrouter/catalog_ops.py` | `agentrouter-registry::catalog_ops` | Partial |
| `agentrouter/classifier.py` | `agentrouter-classifier` | Parity |
| `agentrouter/cli.py` | `agentrouter-cli::bin::agentrouter` plus command modules | Partial |
| `agentrouter/context_model.py` | `agentrouter-classifier::context_model` | Parity |
| `agentrouter/contract.py` | `—` | Not ported |
| `agentrouter/controls.py` | `agentrouter-policy::controls` | Parity |
| `agentrouter/dashboard.py` | `agentrouter-cli::dashboard` | Partial |
| `agentrouter/diagnostics.py` | `agentrouter-cli::diagnostics` | Partial |
| `agentrouter/engine.py` | `agentrouter-routing` | Parity |
| `agentrouter/evaluate.py` | `agentrouter-evaluation::legacy_gold` | Partial |
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
| `agentrouter/evaluation/evaluators/performance.py` | `agentrouter-evaluation::{evaluate_performance,summarize_performance}` | Partial |
| `agentrouter/evaluation/evaluators/platform.py` | `agentrouter-evaluation::evaluate_platform` | Partial |
| `agentrouter/evaluation/evaluators/provider.py` | `agentrouter-evaluation::evaluate_provider` | Partial |
| `agentrouter/evaluation/evaluators/routing.py` | `agentrouter-evaluation::evaluate_routing` | Partial |
| `agentrouter/evaluation/evaluators/safety.py` | `agentrouter-evaluation::evaluate_safety` | Partial |
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
| `agentrouter/openai_adapter.py` | `agentrouter-cli::openai` | Partial |
| `agentrouter/plugins.py` | `—` | Not ported |
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
| `agentrouter/store.py` | `agentrouter-storage` | Partial |
| `agentrouter/taxonomy.py` | `agentrouter-policy::taxonomy` | Parity |
| `agentrouter/usage.py` | `agentrouter-usage::{check_usage,apply_live_verification}` | Partial |

## Release interpretation

- The Rust workspace has no `TODO`, `todo!()`, or `unimplemented!()` markers in
  shipped Rust source, but that does not make unported Python behavior complete.
- The Python modules marked **Partial** and **Not ported** remain production
  responsibilities. The CLI, HTTP, MCP, plugin/skill, evaluation/annotation,
  diagnostic-bundle, and reliability surfaces still have Rust contract gaps.
- The Rust MCP process implements the five Python tools and stdio lifecycle;
  protocol/tool and result differentials cover all five. The unified CLI now
  runs this stdio server in-process with the selected AgentRouter home. Broader
  cross-version lifecycle/error and command-line behavior remain under
  compatibility review, so the module is Partial.
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
- The historical classifier and routing-gold evaluator, report rendering, and
  artifact writing are implemented in Rust and differentially checked against
  the full checked-in gold sets. Python's typed `GoldError` surface and exact
  JSON text escaping still differ; the module remains Partial. See
  [`RUST_LEGACY_GOLD.md`](RUST_LEGACY_GOLD.md).
- Rust `Classification` now rejects unknown fields and has round-trip and
  rejection checks against Pydantic. Python's unbounded integer and scalar
  coercion behavior is not fully represented by the Rust integer/serde types,
  so the schema module remains Partial.
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
- Classification-only grading and gate calculation have differential coverage;
  Rust does not invoke the classifier or implement the `measure_all` evaluators.
- The safety evaluator now classifies and gates cases in Rust with differential
  coverage. Feedback, provider, routing, platform, and performance each have
  partial or complete Rust scoring, while runtime orchestration remains open.
- Provider metadata scoring is ported over caller-supplied model records; Rust
  does not load the packaged seed registry for this evaluator yet.
- The feedback/storage evaluator now uses the Rust SQLite store in a unique
  temporary home and compares the same decision, feedback, and aggregation
  checks. The platform evaluator matches scoring for a caller-supplied CLI
  command/group manifest; runtime Typer command discovery remains Python-only.
- The Rust limits module matches fixed-window rate checks, retry-after values,
  response TTL and media type, and per-key single-flight semantics. It is a
  process-local primitive; the HTTP middleware and server request lifecycle
  still run through Python.
- Rust catalog operations now include provenance reads, freshness summaries,
  sorted generated-catalog listing and deprecation reports, plus rollback and
  restore with raw-byte preservation, exclusive backup creation, linked-file
  refusal and no-clobber restoration. Python-compatible behavior is
  differentially tested; typed `CatalogError` and all error-message edge cases
  remain open, so the module is still Partial.
- The Rust SDK client covers Python endpoint paths, payload cleanup, an
  optional API-key header, timeout configuration and structured HTTP errors.
  The local HTTP server and end-to-end client/server contract remain
  Python-only; redirects are disabled so a key cannot be forwarded elsewhere.
- The Rust API crate now ports classify, route, feedback and dry-run request
  bounds, typed response models, and passthrough envelopes that preserve
  engine-owned fields. Differential checks cover supported Pydantic boolean and
  integer coercions and field-level 422 responses; Python's unbounded integer
  range, some docs behavior, and parts of the server lifecycle remain unported,
  so the HTTP schema module is Partial. The TypeScript SDK exercises all
  manifest operations against the Rust process in the cross-platform CI job.
- Rust API service functions now match Python model and host listings,
  classification, no-log and persisted routing, decision lookup, nullable-note
  feedback, and dry-run previews using committed local registries and SQLite.
  Rust now serves those functions over Axum, and the TypeScript SDK drives every
  manifest operation against that process. FastAPI middleware/observability
  edge cases and the full context-token integer range remain open, so service
  parity is Partial.
- Performance scoring and classification/routing timing now run in Rust for
  caller-supplied models and tasks. Seed loading and injected classifier
  behavior remain Python-side; latency values are machine-dependent.
- Baseline/current comparison scoring, UTF-8 result loading, and Markdown/CSV
  artifact generation match Python.
- The AgentRouter gold adapter now matches Python metadata, availability, description, all 165 records, checksums, and deterministic sampling; the full behavior is differentially tested, including Unicode/default handling.
- Shared fixture-mode evaluation adapter behavior now matches six fixture-backed adapters for metadata, availability, description, JSONL record loading/checksums, deterministic sampling, and explicit skipped-external behavior. Real dataset downloads, preparation, and adapter-specific real-data mappings remain Python-only.
- Evaluation provenance now matches Python for dataset-quality/leakage aggregation and the complete four-field runtime environment snapshot.
- Routing evaluation now scores caller-supplied model catalogs against gold
  constraints or the declared distinct-fallback proxy. Loading seed models and
  custom classifier injection remain Python-only.
- This table is a release checklist, not a replacement for CI evidence. Add a
  differential suite before moving any row to **Parity**.
