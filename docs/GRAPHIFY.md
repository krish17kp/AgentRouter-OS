# Graphify integration policy

Graphify is the repository knowledge / impact-analysis layer for AgentRouter OS.
It is a **development aid only** — no production code depends on it.

## Package identity (verified 2026-07-20)

- Package: **`graphifyy`** (official) — the command it provides is `graphify`.
- Version: **0.9.30**.
- Executable: `~/.local/bin/graphify` (also `graphify-mcp`).
- Install scope: isolated **uv tool** environment (`uv tool list` shows `graphifyy v0.9.30`).
  It is NOT a dependency of the `agentrouter` package and never appears in `pyproject.toml`.
- Provenance: the `graphify` binary on PATH resolves to the official `graphifyy` uv tool,
  not an unrelated same-named package. `python -m pip show graphifyy` returns nothing in the
  project venv precisely because it is uv-tool-isolated, which is the intended separation.

## Install policy — CLI-direct, no global skill

`graphify install --platform claude` in this CLI version copies the skill into the **global**
`~/.claude` config and has no `--project` flag. command.md requires project-local installation
that never overwrites the existing production-loop hooks/agents/skills, and forbids installing
globally when a local approach suffices. It does: the `graphify` CLI builds and queries the graph
directly, so we **use the CLI** (`graphify update .`, `graphify explain`, `graphify path`,
`graphify diagnose`) and do **not** install the global Claude skill. The project `.claude/`
control plane (7 agents, 3 hooks, settings.json) is therefore untouched.

## Exclusions

- `.claudeignore` (new) keeps `graphify-out/`, secrets, virtualenvs, caches, build output and
  generated artifacts out of Claude prompt-cache scanning.
- `.gitignore` ignores `graphify-out/`, `graph.html`, `raw/`, and the `.mutmut-cache` file.
- Verified after the first build: **0 excluded-dir paths** (`.venv`, `node_modules`, `mutants`,
  `dist`, `build`) and **0 secret-like strings** in `graphify-out/graph.json`.

## Version-control policy

`graphify-out/` (graph.json, GRAPH_REPORT.md, graph.html) is **generated and gitignored** — not
committed. It is large, machine-specific, and rebuildable from source via `graphify update .`.
The durable, reviewed artifact is `docs/GRAPHIFY_BASELINE.md` (committed). If a shareable graph is
ever needed, export a pruned `graph.json` deliberately after a secret re-scan; never auto-commit.

## Usage in the loop

- Build / refresh: `graphify update .` (AST extraction + clustering, no LLM, no network).
- Discovery before editing a shared module: `graphify explain "<node>"`.
- Impact / reverse-deps: `graphify path "<A>" "<B>"`, plus `explain` (shows callers via `<--`).
- Per task: write `loop/tasks/<TASK>/graph-discovery.md` and `graph-impact-before/after.md`.
- After each completed task: `graphify update .`, then re-query the changed subsystem.
- Every 5 tasks / major change: full rebuild + baseline refresh.

Never treat an inferred edge (`indirect_call`, `references`) as verified truth without opening the
cited `source_file:source_location`.
