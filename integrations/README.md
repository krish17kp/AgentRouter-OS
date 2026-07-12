# Integrations — use AgentRouter inside any agent CLI/IDE

AgentRouter's integration surface is deliberately thin: the CLI already speaks
stable JSON (`route --json`), so "integration" is instructions, not code. Two
artifacts cover every host:

| Artifact | For |
|---|---|
| [`claude-code/agentrouter/SKILL.md`](claude-code/agentrouter/SKILL.md) | Claude Code (full skill: modes, decomposition, tier mapping) |
| [`AGENTS.md`](AGENTS.md) | Everything else (Codex, Antigravity, Cursor, generic system prompts) |

Both implement the same protocol: **host agent decomposes → AgentRouter routes
each subtask → host maps the recommended pricing tier onto its own models →
cheap subtasks run on cheap models.** High-risk subtasks are never
auto-executed in any mode.

## Install

Prerequisite everywhere: `pip install agentrouter-os && agentrouter init`.

**Claude Code** — copy the skill folder:

```bash
# user-level (all projects)
cp -r integrations/claude-code/agentrouter ~/.claude/skills/agentrouter
# or project-level
cp -r integrations/claude-code/agentrouter .claude/skills/agentrouter
```

Then: "route this task" / "use agentrouter in auto mode" in any session.

**Codex CLI** — append `integrations/AGENTS.md` to the repo's `AGENTS.md`
(Codex reads it automatically).

**Antigravity / Gemini** — paste the protocol section from
`integrations/AGENTS.md` into the workspace rules file.

**Cursor** — paste it into `.cursorrules` (or a `.cursor/rules/` file).

**Anything else** — it's a markdown instruction block plus a CLI on PATH;
paste it wherever that host reads standing instructions.

## Modes

- **manual** (default): recommend + explain, user decides.
- **auto**: decompose → route per subtask → execute on mapped host models
  (subagents where supported), gated so `risk=high` always requires a human.
