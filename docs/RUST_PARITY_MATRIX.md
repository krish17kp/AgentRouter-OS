# Python-to-Rust parity inventory

Updated: 2026-11-11. This inventory covers every Python source module under
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
| `agentrouter/__main__.py` | `—` | Not ported |
| `agentrouter/annotation/__init__.py` | `agentrouter-evaluation::annotation_api` | Parity |
| `agentrouter/annotation/adjudicate.py` | `agentrouter-evaluation::{annotation_needs_adjudication,resolve_annotation}` | Parity |
| `agentrouter/annotation/candidates.py` | `agentrouter-evaluation::annotation_candidates` | Parity |
| `agentrouter/annotation/cli.py` | `—` | Not ported |
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
| `agentrouter/cli.py` | `agentrouter-cli probes` | Partial |
| `agentrouter/context_model.py` | `agentrouter-classifier::context_model` | Parity |
| `agentrouter/contract.py` | `—` | Not ported |
| `agentrouter/controls.py` | `agentrouter-policy::controls` | Parity |
| `agentrouter/dashboard.py` | `agentrouter-cli::dashboard` | Partial |
| `agentrouter/diagnostics.py` | `agentrouter-cli::diagnostics` | Partial |
| `agentrouter/engine.py` | `agentrouter-routing` | Parity |
| `agentrouter/evaluate.py` | `—` | Not ported |
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
| `agentrouter/evaluation/cli.py` | `—` | Not ported |
| `agentrouter/evaluation/comparison.py` | `agentrouter-evaluation::{compare_results,load_result,write_comparison}` | Parity |
| `agentrouter/evaluation/context_bands.py` | `agentrouter-evaluation::context_bands` | Parity |
| `agentrouter/evaluation/evaluators/__init__.py` | `agentrouter-evaluation::evaluators_api` | Partial |
| `agentrouter/evaluation/evaluators/feedback.py` | `agentrouter-evaluation::evaluate_feedback` | Parity |
| `agentrouter/evaluation/evaluators/performance.py` | `agentrouter-evaluation::{evaluate_performance,summarize_performance}` | Partial |
| `agentrouter/evaluation/evaluators/platform.py` | `agentrouter-evaluation::evaluate_platform` | Partial |
| `agentrouter/evaluation/evaluators/provider.py` | `agentrouter-evaluation::evaluate_provider` | Partial |
| `agentrouter/evaluation/evaluators/routing.py` | `agentrouter-evaluation::evaluate_routing` | Partial |
| `agentrouter/evaluation/evaluators/safety.py` | `agentrouter-evaluation::evaluate_safety` | Partial |
| `agentrouter/evaluation/grading.py` | `agentrouter-evaluation::grade_classification` | Partial |
| `agentrouter/evaluation/metrics.py` | `agentrouter-evaluation::classification_metrics` | Parity |
| `agentrouter/evaluation/provenance.py` | `agentrouter-evaluation::{dataset_quality,environment_snapshot}` | Parity |
| `agentrouter/evaluation/registry.py` | `agentrouter-evaluation::profile_datasets` | Partial |
| `agentrouter/evaluation/reports.py` | `agentrouter-evaluation::{render_markdown, write_reports}` | Parity |
| `agentrouter/evaluation/runner.py` | `—` | Not ported |
| `agentrouter/evaluation/sampling.py` | `agentrouter-evaluation::deterministic_sample` | Parity |
| `agentrouter/evaluation/schema.py` | `agentrouter-evaluation::{EvaluationCase,ExpectedClassification,Provenance,normalized_hash}` | Parity |
| `agentrouter/harness.py` | `agentrouter-cli::harness` | Parity |
| `agentrouter/hosts.py` | `agentrouter-hosts` | Parity |
| `agentrouter/learning.py` | `agentrouter-learning::learned_weights` | Parity |
| `agentrouter/mcp_server.py` | `—` | Not ported |
| `agentrouter/observability.py` | `agentrouter-cli::observability` | Partial |
| `agentrouter/openai_adapter.py` | `agentrouter-cli::openai` | Partial |
| `agentrouter/plugins.py` | `—` | Not ported |
| `agentrouter/prompts.py` | `agentrouter-cli::generate_prompt` | Parity |
| `agentrouter/refresh.py` | `—` | Not ported |
| `agentrouter/registry.py` | `agentrouter-registry` | Parity |
| `agentrouter/reliability/__init__.py` | `—` | Not ported |
| `agentrouter/reliability/harness.py` | `—` | Not ported |
| `agentrouter/reliability/soak.py` | `—` | Not ported |
| `agentrouter/safety.py` | `agentrouter-policy` | Parity |
| `agentrouter/schema.py` | `agentrouter-core + agentrouter-registry` | Partial |
| `agentrouter/sdk.py` | `—` | Not ported |
| `agentrouter/server/__init__.py` | `agentrouter-evaluation::package_markers::SERVER_PUBLIC_EXPORTS` | Parity |
| `agentrouter/server/app.py` | `—` | Not ported |
| `agentrouter/server/limits.py` | `—` | Not ported |
| `agentrouter/server/schemas.py` | `—` | Not ported |
| `agentrouter/server/service.py` | `—` | Not ported |
| `agentrouter/store.py` | `agentrouter-storage` | Partial |
| `agentrouter/taxonomy.py` | `agentrouter-policy::taxonomy` | Parity |
| `agentrouter/usage.py` | `agentrouter-usage::{check_usage,apply_live_verification}` | Partial |

## Release interpretation

- The Rust workspace has no `TODO`, `todo!()`, or `unimplemented!()` markers in
  shipped Rust source, but that does not make unported Python behavior complete.
- The Python modules marked **Partial** and **Not ported** remain production
  responsibilities. The CLI, HTTP, MCP, plugin/skill, evaluation/annotation,
  diagnostic-bundle, and reliability surfaces still need their Rust contract
  implementations and differential tests.
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
