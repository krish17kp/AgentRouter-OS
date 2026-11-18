# TASK-151 — Apply routing research to the evaluation plan

## Goal

Use current open research and router documentation to make AgentRouter's routing
improvement path measurable and safe.

## Scope

- Record reproducible findings from LiteLLM, RouteLLM, RouterBench, and
  LLMRouterBench using primary documentation and papers.
- Translate findings into AgentRouter baselines, model-pool practice, retry
  ownership, and release constraints.
- Preserve disabled-by-default learned/cascade routing until independent data
  and evaluation gates support promotion.

## Acceptance

- The research document contains linked primary sources and concrete project
  decisions.
- The evaluation protocol requires a best-single baseline, common workload and
  model pool, quality/cost/latency reporting, and an untouched promotion set.
- No model, threshold, release gate, or frozen label is changed by this task.
