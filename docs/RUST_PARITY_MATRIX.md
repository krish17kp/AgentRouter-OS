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
| `agentrouter/__init__.py` | `—` | Not ported |
| `agentrouter/__main__.py` | `—` | Not ported |
| `agentrouter/annotation/__init__.py` | `—` | Not ported |
| `agentrouter/annotation/adjudicate.py` | `—` | Not ported |
| `agentrouter/annotation/candidates.py` | `—` | Not ported |
| `agentrouter/annotation/cli.py` | `—` | Not ported |
| `agentrouter/annotation/compare.py` | `—` | Not ported |
| `agentrouter/annotation/dedup.py` | `—` | Not ported |
| `agentrouter/annotation/graph_signals.py` | `—` | Not ported |
| `agentrouter/annotation/packs.py` | `—` | Not ported |
| `agentrouter/annotation/schema.py` | `—` | Not ported |
| `agentrouter/annotation/splits.py` | `—` | Not ported |
| `agentrouter/annotation/store.py` | `—` | Not ported |
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
| `agentrouter/evaluation/__init__.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/__init__.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/agentrouter_gold.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/banking77.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/clinc150.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/llmrouterbench.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/longbench_v2.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/massive.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/swebench.py` | `—` | Not ported |
| `agentrouter/evaluation/adapters/twinrouterbench.py` | `—` | Not ported |
| `agentrouter/evaluation/base.py` | `—` | Not ported |
| `agentrouter/evaluation/cli.py` | `—` | Not ported |
| `agentrouter/evaluation/comparison.py` | `—` | Not ported |
| `agentrouter/evaluation/context_bands.py` | `—` | Not ported |
| `agentrouter/evaluation/evaluators/__init__.py` | `—` | Not ported |
| `agentrouter/evaluation/evaluators/feedback.py` | `agentrouter-evaluation::evaluate_feedback` | Parity |
| `agentrouter/evaluation/evaluators/performance.py` | `agentrouter-evaluation::{evaluate_performance,summarize_performance}` | Partial |
| `agentrouter/evaluation/evaluators/platform.py` | `agentrouter-evaluation::evaluate_platform` | Partial |
| `agentrouter/evaluation/evaluators/provider.py` | `agentrouter-evaluation::evaluate_provider` | Partial |
| `agentrouter/evaluation/evaluators/routing.py` | `agentrouter-evaluation::evaluate_routing` | Partial |
| `agentrouter/evaluation/evaluators/safety.py` | `agentrouter-evaluation::evaluate_safety` | Partial |
| `agentrouter/evaluation/grading.py` | `agentrouter-evaluation::grade_classification` | Partial |
| `agentrouter/evaluation/metrics.py` | `agentrouter-evaluation::classification_metrics` | Parity |
| `agentrouter/evaluation/provenance.py` | `agentrouter-evaluation::dataset_quality` | Partial |
| `agentrouter/evaluation/registry.py` | `agentrouter-evaluation::profile_datasets` | Partial |
| `agentrouter/evaluation/reports.py` | `agentrouter-evaluation::{render_markdown, write_reports}` | Parity |
| `agentrouter/evaluation/runner.py` | `—` | Not ported |
| `agentrouter/evaluation/sampling.py` | `agentrouter-evaluation::deterministic_sample` | Parity |
| `agentrouter/evaluation/schema.py` | `agentrouter-evaluation::EvaluationCase` | Partial |
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
| `agentrouter/server/__init__.py` | `—` | Not ported |
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
- Routing evaluation now scores caller-supplied model catalogs against gold
  constraints or the declared distinct-fallback proxy. Loading seed models and
  custom classifier injection remain Python-only.
- This table is a release checklist, not a replacement for CI evidence. Add a
  differential suite before moving any row to **Parity**.
