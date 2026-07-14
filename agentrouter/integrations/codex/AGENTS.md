# AgentRouter routing protocol (host-agnostic)

Paste this section into any agent's instruction file (`AGENTS.md`,
`.cursorrules`, Antigravity rules, a system prompt, …). It is the same
protocol as the Claude Code skill in `claude-code/agentrouter/SKILL.md`,
condensed for hosts without a skill mechanism.

---

## Model routing with AgentRouter

A local CLI (`agentrouter`, or `python -m agentrouter`) recommends which model
tier should run a task. Setup once: `pip install agentrouter-os && agentrouter init`.

**Manual mode (default):** when the user asks which model to use, run
`agentrouter route --json "<task>"` and present the recommendation, fallback,
`reason`, and safety checklist. Do not act further.

**Auto mode (user asks you to do the work and says "auto"):**

1. Decompose the task into independently executable subtasks (you do this —
   the CLI is rule-based and cannot).
2. For each subtask run `agentrouter route --json "<subtask>"`.
3. Map `recommendation.pricing_tier` to a model available in this environment:
   - `free`/`low` → your smallest model
   - `medium` → your mid/default model
   - `high`/`frontier` → your strongest model
4. Execute each subtask on the mapped model (subagents/parallel where
   supported, sequential otherwise).
5. **Hard gate:** if `classification.risk == "high"` or
   `gates.auto_execute_allowed == false`, never auto-execute — show
   `gates.checklist` and ask the user.
6. Afterwards, optionally: `agentrouter feedback <decision_id> --rating <1-5>`
   (feeds its learning loop).

Don't route trivial one-liners; the overhead exceeds the saving.
Exit code 4 = no eligible model (relax `--context-tokens`/`--tool` overrides).
