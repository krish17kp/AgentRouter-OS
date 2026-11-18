# TASK-151 evidence

Research findings and decisions are in
[`docs/ROUTING_EVOLUTION_2026-11.md`](../../../docs/ROUTING_EVOLUTION_2026-11.md).
Primary sources reviewed:

- [LiteLLM routing reliability documentation](https://docs.litellm.ai/docs/router/learn/reliability).
- [RouteLLM source repository and calibration guidance](https://github.com/lm-sys/RouteLLM).
- [RouterBench paper](https://arxiv.org/abs/2403.12031).
- [LLMRouterBench paper](https://arxiv.org/abs/2601.07206).

The resulting plan requires best-single, cheapest, strongest, and random
baselines, common workload/model pool/pricing snapshots, per-domain and high-risk
reporting, quality/cost/latency metrics, and an untouched promotion set. Learned
and cascade routing remain disabled until independent labels and release
evidence exist. No frozen evaluation inputs or gates changed.
