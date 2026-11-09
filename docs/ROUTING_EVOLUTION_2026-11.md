# Routing evolution and Rust delivery plan

Research date: 2026-11-09. This is an engineering plan, not a release-readiness claim.
Python remains the shipping implementation. The Rust workspace has R1 shared types and
the first static routing decision parity slice; neither is a complete Rust router.

## What comparable systems do

| System | Verified approach | AgentRouter decision |
| --- | --- | --- |
| [LiteLLM Router](https://docs.litellm.ai/docs/router/learn/concepts) | Separates request eligibility, deployment selection, retry within a model group, fallback across groups, and cooldown state. It can select by load, latency, usage, or cost. | Keep AgentRouter's explainable *model* selection separate from *deployment* health and execution. Add health-aware filtering only when measured host outcomes exist; never silently treat an unknown host as healthy. |
| [OpenRouter provider selection](https://github.com/OpenRouterTeam/docs/blob/main/guides/routing/provider-selection.mdx) | Uses measured price, throughput, latency, rate-limit errors, reliability, and tool-call quality; exposes provider pinning, parameter requirements, data-policy restrictions, and fallback controls. | Extend registry evidence with dated, source-labelled observations and hard capability/privacy filters. Never fabricate an effective price or infer support from a model name. |
| [RouteLLM](https://github.com/lm-sys/RouteLLM) and its [paper](https://arxiv.org/abs/2406.18665) | Trains and evaluates cost-versus-quality routing between stronger and weaker models using preference data. | Treat learned routing as a candidate after collecting consented, blinded outcome labels. Compare against static, random, and always-strong baselines on held-out data. Do not train against AgentRouter's frozen release holdout. |
| [Portkey gateway](https://portkey.ai/features/ai-gateway) | Offers configurable conditional routing, retry, fallback, load balancing, timeout, and canary testing. | Add a documented deployment-policy layer and shadow/canary evaluation before live use. Execution adapters remain default-off and require separate authorization. |

These products solve partly different problems. AgentRouter's distinctive requirement is a
local, inspectable decision with policy and safety evidence. Gateway features cannot be
copied wholesale: real latency, cost, failure, and quality signals require real outcomes,
and current provider adapters do not supply them. Vendor marketing numbers are not
accepted as AgentRouter benchmarks.

## Delivery sequence

1. **Parity first.** Build Rust crates behind existing Python contracts: registry
   validation, classification, policy, scoring, fallback, host resolution, then
   SQLite/CLI/HTTP/MCP. Each slice gets Python/Rust differential fixtures, malformed
   input tests, Windows/Linux CI, and a rollback path. The current slice ports
   `engine.weights_for` and the static eligibility/scoring/fallback pass over a
  validated registry projection, plus the static safety gate. Unknown preferences are rejected.
2. **Evidence model.** Define dated observations for provider/deployment health,
   time to first token, throughput, effective price, rate-limit rate, and tool-call
   success. Separate observed values from catalog estimates. Specify expiry,
   minimum sample size, and missing-data behavior before changing scores.
3. **Safer decisions.** Apply hard exclusions for policy, context, tools, privacy,
   and authorized host availability before ranking. Record every exclusion. Keep
   deterministic model scoring as the baseline, then select a healthy deployment
   within the chosen model. A failed deployment may retry within bounded policy;
   cross-model fallback must recheck every hard constraint and approval gate.
4. **Measured optimization.** Add offline replay and shadow evaluation with
   quality, cost, latency, abstention, fallback rate, and safety violations.
   Compare fixed weights to cost-sensitive and learned candidates. Promote only
   on a separate untouched test set and preserve the existing seven release gates.
5. **Operational completion.** Ship execution only after adapter lifecycle tests
   cover cancellation, timeout, retries, budgets, malformed output, and audit
   redaction. Then complete orchestration, annotation tooling, and the Rust-only
   validation and rollback drill specified in `RUST_MIGRATION_PLAN.md` R6–R13.

## Current gates and blockers

- `RUST_MIGRATION_PLAN.md` remains the authoritative milestone and Python-retirement
  contract. Static route parity is partial progress, not completion of R2/R3.
- The frozen context-band holdout is below its unchanged 0.90 gate according to
  `RELEASE_READINESS.md`. The two-human annotation/adjudication round in
  `TASK_012_OWNER_ACTIONS.md` is required; AI-generated labels cannot close it.
- Live outcome metrics and provider execution require owner-selected providers,
  credentials, consent/data policy, and separately authorized execution. This
  plan does not turn on remote execution or collect prompt content.
- Rust cannot replace Python until the existing CLI/HTTP/MCP/SQLite contracts,
  evaluation gates, security and mutation thresholds, cross-platform CI,
  staging evidence, and rollback drill all pass as documented in the migration plan.

## Immediate acceptance checks

- `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`,
  and `cargo test --workspace` pass.
- `tests/test_rust_routing_weights.py` compares nine Python/Rust weight-policy
  scenarios and rejects an unknown preference. `tests/test_rust_routing_decision.py`
  compares the full static route on 30 task/constraint combinations from the
  seed registry, including no-eligible and fallback cases. `tests/test_rust_safety_parity.py`
  covers all nine risk/approval gate combinations.
- No Python behavior changes or release threshold changes are made by this slice.
