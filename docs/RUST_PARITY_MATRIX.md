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
| `agentrouter/bundle.py` | `—` | Not ported |
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
| `agentrouter/evaluation/evaluators/feedback.py` | `—` | Not ported |
| `agentrouter/evaluation/evaluators/performance.py` | `—` | Not ported |
| `agentrouter/evaluation/evaluators/platform.py` | `—` | Not ported |
| `agentrouter/evaluation/evaluators/provider.py` | `—` | Not ported |
| `agentrouter/evaluation/evaluators/routing.py` | `—` | Not ported |
| `agentrouter/evaluation/evaluators/safety.py` | `—` | Not ported |
| `agentrouter/evaluation/grading.py` | `—` | Not ported |
| `agentrouter/evaluation/metrics.py` | `—` | Not ported |
| `agentrouter/evaluation/provenance.py` | `—` | Not ported |
| `agentrouter/evaluation/registry.py` | `—` | Not ported |
| `agentrouter/evaluation/reports.py` | `—` | Not ported |
| `agentrouter/evaluation/runner.py` | `—` | Not ported |
| `agentrouter/evaluation/sampling.py` | `—` | Not ported |
| `agentrouter/evaluation/schema.py` | `—` | Not ported |
| `agentrouter/harness.py` | `agentrouter-cli::harness` | Parity |
| `agentrouter/hosts.py` | `agentrouter-hosts` | Parity |
| `agentrouter/learning.py` | `agentrouter-cli + agentrouter-storage` | Partial |
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
| `agentrouter/usage.py` | `agentrouter-usage` | Partial |

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
- This table is a release checklist, not a replacement for CI evidence. Add a
  differential suite before moving any row to **Parity**.
