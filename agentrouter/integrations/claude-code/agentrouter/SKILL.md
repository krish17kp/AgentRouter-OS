---
name: agentrouter
description: Route tasks and subtasks to the right model tier using the AgentRouter OS CLI. Use when the user asks to route a task, pick the best model, split work across models to save tokens, or says "agentrouter", "route this", "auto mode", or "manual mode". Decomposes big tasks into subtasks, routes each one, and maps recommendations onto the models available in this environment.
---

# AgentRouter — model routing skill

You are the **host agent** (Claude Code, Codex, Antigravity, Cursor, any CLI/IDE
agent). AgentRouter is a local CLI that answers one question per task:
*which tier of model should run this, and why* — with a fallback, a safety
checklist, and a logged, explainable decision.

Division of labor (this is the whole trick):

- **You decompose.** You are an LLM; the CLI is rule-based. Splitting a task
  into subtasks is your job.
- **AgentRouter routes.** For each subtask it returns the cheapest tier that is
  actually adequate, so cheap subtasks stop burning frontier-model tokens.
- **You execute.** Map each recommendation onto a model that exists in *this*
  environment and run the subtask there (subagent with a model override where
  the host supports it; otherwise sequential with per-step model choice).

## Requirements

```bash
pip install agentrouter-os     # or: pip install -e . from the repo
agentrouter init               # one-time; creates ~/.agentrouter/
```

If `agentrouter` is not on PATH, `python -m agentrouter` is equivalent.

## Modes

Default is **manual**. The user picks the mode by saying "auto" / "manual",
or you infer auto when they ask you to *do* the work, manual when they ask
*which model* to use.

### Manual mode — recommend, then wait

1. `agentrouter route --json "<task>"`
2. Present: recommendation + fallback, the one-line `reason`, the safety
   `gates.checklist`, and the `decision_id`.
3. Stop. The user decides what runs where.

### Auto mode — decompose, route, execute

1. **Plan.** Break the task into the smallest subtasks that are independently
   executable (e.g. search → analyze → write). Don't force a split — a task
   that is one unit stays one unit.
2. **Route each subtask:**
   `agentrouter route --json "<subtask>" [--risk high] [--context-tokens N]`
   Override the classifier when you know better than the keywords.
3. **Map the recommendation to a host model** via `recommendation.pricing_tier`
   (see table below). The registry model name itself may not exist in your
   environment — the *tier* is what transfers.
4. **Execute** each subtask on the mapped model — as parallel subagents when
   the host supports model-per-subagent and the subtasks are independent;
   otherwise sequentially.
5. **Respect the gates — hard rule.** If `classification.risk == "high"` or
   `gates.auto_execute_allowed == false`: do NOT auto-execute that subtask.
   Show the checklist and ask the user first. This mirrors the CLI's own
   NFR-8 gate; auto mode never overrides it.
6. **Close the loop (optional but encouraged).** After a subtask completes:
   `agentrouter feedback <decision_id> --rating <1-5>` — ratings feed the
   bounded learning loop, so routing improves with use.

## Tier → host model mapping

`recommendation.pricing_tier` is one of `free | low | medium | high | frontier`.

| Tier | Claude Code | Codex CLI | Antigravity / Gemini | Generic rule |
|---|---|---|---|---|
| free / low | haiku | gpt-*-mini / -nano | flash | smallest available |
| medium | sonnet | gpt-4.1 / default | pro | mid / default model |
| high / frontier | opus | o3 / largest | ultra / largest | strongest available |

If the host exposes only one model, mapping collapses to "use it" — manual
mode is then the useful mode (the recommendation still tells the user what to
open elsewhere).

In Claude Code specifically: run subtasks via the Agent tool with a `model`
override (`haiku` / `sonnet` / `opus`) per the table.

## Worked example (auto mode)

Task: *"Research how competitors price API products and write a comparison doc."*

```
subtask 1  "search the web for competitor API pricing pages"   → low tier    → haiku subagent
subtask 2  "extract and normalize pricing into a table"        → medium tier → sonnet subagent
subtask 3  "write the final comparison document"               → medium/high → sonnet or opus
```

Three `agentrouter route --json` calls, three decision ids, cheap work on
cheap models. That is the token saving.

## JSON fields you will use

| Field | Use |
|---|---|
| `recommendation.pricing_tier` | drives the host-model mapping |
| `recommendation.model`, `fallback` | what to report / retry with |
| `reason` | one-line justification to show the user |
| `classification.risk`, `gates.auto_execute_allowed` | the execution gate |
| `gates.checklist` | show before any risky step |
| `decision_id` | for `explain` and `feedback` |
| `prompt` | ready-made execution prompt for the subtask |

Exit codes: `0` ok · `3` broken registry/config (tell the user) · `4` no
eligible model (relax overrides or use `manual_suggestion`).

## Rules

- Never auto-execute a high-risk subtask. No exceptions in any mode.
- Don't route trivial one-liners ("fix this typo") — routing overhead exceeds
  the saving; just do them.
- One `route` call per subtask, not per file/step — subtask granularity.
- If `agentrouter` isn't installed or `init` hasn't run, say so and give the
  two setup commands instead of failing silently.
