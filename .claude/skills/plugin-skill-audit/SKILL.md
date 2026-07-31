---
name: plugin-skill-audit
description: Inventory and evaluate the plugins, skills, agents, hooks and MCP servers available to this project, and decide use/disable/conditional. Use when the user asks to audit tooling, "run /doctor", or before relying on a new plugin/skill.
context: fork
---

# Plugin / Skill Audit

1. Inspect scopes: bundled skills, `.claude/skills`, `~/.claude/skills`,
   `.claude/agents`, `~/.claude/agents`, plugin manifests, `.mcp.json`, and
   `.claude/settings*.json`. NEVER print secret values.
2. For each component record: name, type, scope, enabled, permissions (write/
   network/secret), relevance to this Python routing project, known conflicts,
   and a recommendation: use / use_conditionally / disable / replace / needs_review.
3. Reject components with unjustified write/network/secret access. Prefer the
   smallest effective toolset; avoid duplicate agents with the same role.
4. Where the skill-creator plugin is available, measure should-trigger /
   should-not-trigger / output quality / with-vs-without / token overhead.
5. Write `loop/PLUGIN_SKILL_INVENTORY.yaml` + `loop/PLUGIN_SKILL_DECISIONS.md`.
   Do not claim a skill was evaluated unless the eval actually ran
   (evals go to `loop/reports/skill-evals/`).
