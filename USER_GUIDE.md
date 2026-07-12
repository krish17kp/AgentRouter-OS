# AgentRouter OS — User Guide

Practical walkthrough of every command. Assumes install per
[README.md](README.md) quick start. All data stays local under
`~/.agentrouter/` (override with the `AGENTROUTER_HOME` env var).

---

## 1. `init` — set up

```console
$ agentrouter init            # creates config, seed registries, empty decision log
$ agentrouter init --force    # re-seed, overwriting your edits
```

Safe to re-run: existing files are skipped unless `--force`.

## 2. `registry list` — see what's routable

```console
$ agentrouter registry list                       # everything
$ agentrouter registry list --provider openrouter --active-only
$ agentrouter registry list --json                # machine-readable
```

The registry is *yours*: edit `~/.agentrouter/registry/models.yaml` to add,
reprice, or retire models (fields documented in
[MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md)). Changes apply on the
next command — no restart, no code.

## 3. `route` — the core command

```console
$ agentrouter route "Polish the README for a Python CLI project"
```

Output sections, top to bottom:
1. **How I read this task** — the 7-dimension classification.
2. **Recommendation** — best model + one fallback, with scores.
3. **Why** — one-line plain-English justification.
4. **Safety checklist** — scaled to the risk level.
5. **Decision id** + next-command hints.

### Overriding the classifier

The classifier is keyword-based; when it misreads, you win:

```console
$ agentrouter route "tweak the thing" --risk high --tool file-edit,shell --context-tokens 150000
```

### Privacy / scripting flags

```console
$ agentrouter route "..." --no-log     # don't store the task text
$ agentrouter route "..." --json       # machine-readable (see contract below)
```

## 4. `explain <id>` — replay a decision

```console
$ agentrouter explain d_00002
$ agentrouter explain d_00002 --json
```

Shows the stored classification, every excluded model **with the reason**, the
full score table (capability/cost/latency/context/adjust per model), the weight
shifts applied, and the safety gate. Nothing is recomputed — it is an audit
replay of what `route` decided.

## 5. `prompt generate` — get the execution prompt

```console
$ agentrouter prompt generate --from d_00002 --out prompt.md   # from a logged decision
$ agentrouter prompt generate "write release notes" --tool openai/general-purpose-model
```

Paste the generated prompt into the recommended tool — or use `execute` (§8)
if you have opted a provider into execution.

## 6. `feedback <id>` — record the outcome (feeds learning)

```console
$ agentrouter feedback d_00002 --rating 5 --note "worked, tests passed"
```

Ratings feed the **bounded learning loop (M4)**: once 3+ ratings exist, each
low rating (≤2) shifts a little weight (0.01) from cost toward capability —
capped at +0.10 total, never below `w_cost` 0.05. The adaptation is recomputed
from the feedback table on every route (no hidden state), shows up in the
decision's `weight_shifts`, and reverts if you delete feedback rows or set
`learning: false` in `config.yaml`.

## 7. `providers refresh` — live catalog sync (OpenRouter, OpenAI)

```console
$ agentrouter providers refresh openrouter --dry-run     # preview, write nothing
$ agentrouter providers refresh openrouter --limit 15    # import up to 15 models
$ agentrouter providers refresh openrouter --match claude  # only ids containing "claude"
$ OPENAI_API_KEY=sk-... agentrouter providers refresh openai
```

Fetches OpenRouter's live model catalog and writes it to
`~/.agentrouter/registry/models.openrouter.generated.yaml`. How it behaves:

- **Your manual `models.yaml` is never touched** and always wins if a
  generated entry has the same provider + model_id. Delete the
  `.generated.yaml` file to revert to the manual registry.
- **No API key required** — the catalog endpoint is public. If
  `OPENROUTER_API_KEY` is set in your environment it is sent as an auth
  header; it is never printed or logged.
- Re-running converges (the file is rewritten wholesale, no duplicates).
- **OpenAI specifics:** requires `OPENAI_API_KEY` (read-only is enough). The
  API exposes no context/pricing metadata, so entries are mapped from a static
  family table (gpt-4o, gpt-4.1, gpt-5, o3, o4-mini, …); unknown/non-chat
  entries are skipped with one aggregate warning.
- **Honesty note:** refreshed `ability` scores are heuristics (marked in each
  entry's `notes`). To curate them without touching generated files, add
  `~/.agentrouter/registry/ability_overrides.yaml`:

  ```yaml
  overrides:
    openrouter/anthropic/claude-x: { coding: 9, reasoning: 9 }
  ```

  Overrides survive every re-refresh; partial score maps are fine.
- Entries whose `last_updated` ages past 90 days trigger a load-time warning.
- Other providers (`claude-code`, `cursor`, …) are not refreshable; the
  command says so and exits with code 2.

### Live smoke test (needs internet; pytest never does)

```console
$ agentrouter providers refresh openrouter --limit 8 --dry-run   # expect a model table
$ agentrouter providers refresh openrouter --limit 15
$ agentrouter registry list                                       # merged catalog
$ agentrouter route "Summarize a 300k-token repository"           # long-ctx imports compete
```

On network failure the command exits 1, explains itself, and guarantees the
registry was not modified — routing keeps working from the manual registry.

## 8. `execute <id>` — optionally run the recommendation (M6, opt-in)

```console
$ agentrouter execute d_00002          # shows what would run, asks for --yes
$ agentrouter execute d_00002 --yes    # actually runs it
```

Disabled everywhere by default. To opt a provider in, edit
`~/.agentrouter/registry/providers.yaml`:

```yaml
- id: claude-code
  adapter: claude-code
  auth_model: oauth
  supports_execution: true            # your explicit opt-in
  exec_command: ["claude", "-p", "{prompt}"]
```

`{prompt}` is replaced with the decision's generated prompt and run without a
shell. Hard gate (NFR-8): decisions with `risk=high` or any non-auto approval
level are **always blocked** — the command tells you to run the prompt
yourself. The subprocess exit code is propagated.

## 9. `stats` — local telemetry

```console
$ agentrouter stats            # decisions, risk/tier/user distributions, feedback
$ agentrouter stats --json
```

Every decision records who made it: the `AGENTROUTER_USER` env var if set
(recommended in team mode), else your OS username. `stats` shows a `by_user`
breakdown and `explain --json` includes the `user`. Databases created before
v0.4.0 migrate automatically (old rows show as `unknown`).

## 10. `dashboard` — read-only web view

```console
$ agentrouter dashboard              # http://127.0.0.1:8321/
$ agentrouter dashboard --port 0     # any free port
```

Serves decision history, risk/tier distributions, and feedback acceptance from
the local SQLite db. Stdlib HTTP, GET-only — there is no write path from the
dashboard into routing.

## 11. Team mode (shared home) + policy

Point everyone's `AGENTROUTER_HOME` at one shared directory to share the
registry, config, and policy. In the shared `config.yaml`:

```yaml
policy:
  max_pricing_tier: medium   # routing never recommends above this tier
learning: true               # set false to freeze weights
```

The decision log lives in the same directory — fine for a small trusted team,
not multi-tenant hosting (see TODO.md). Have each teammate set
`AGENTROUTER_USER` so `stats` and the dashboard attribute decisions correctly:

```console
$ export AGENTROUTER_USER=alice     # or setx on Windows
```

## 12. Using AgentRouter inside Claude Code / Codex / Antigravity / any agent

The `integrations/` directory ships a skill that lets agent CLIs and IDEs call
AgentRouter themselves: the host agent decomposes a task into subtasks, routes
each one (`route --json`), maps the recommended `pricing_tier` onto its own
models, and runs cheap subtasks on cheap models — saving tokens. Manual mode
recommends only; auto mode executes, but `risk=high` is never auto-run.

```console
$ cp -r integrations/claude-code/agentrouter ~/.claude/skills/agentrouter   # Claude Code
# other hosts: paste integrations/AGENTS.md into the host's instruction file
```

See [integrations/README.md](integrations/README.md) for per-host install.

---

## JSON output contract

`route --json` and `explain --json` emit one JSON object with these stable
top-level keys (scripts can rely on them):

| Key | Type | Meaning |
|---|---|---|
| `decision_id` | string \| null | `d_00042`-style id (null with `--no-log`; explain: always set) |
| `task` | string | The raw task text |
| `classification` | object | The 7 dimensions (`task_type`, `complexity`, `risk`, `context_tokens`, `context_band`, `output_type`, `tool_needs`, `approval_level`) |
| `weights` | object | `w_cap/w_cost/w_lat/w_ctx` actually used |
| `weight_shifts` | array[string] | Human-readable weight adjustments applied |
| `excluded` | array[{model, reason}] | Models removed by hard filters |
| `scores` | array | Ranked rows: `{model, provider, model_id, pricing_tier, terms{cap,cost,lat,ctx,adj,dep}, score}` |
| `recommendation` | object \| null | Top-ranked score row |
| `fallback` | object \| null | Fallback score row |
| `manual_suggestion` | string \| null | Set when nothing was eligible |
| `reason` | string \| null | The one-line "Why" |
| `gates` | object | `{checklist: [...], auto_execute_allowed, approval_level}` |
| `prompt` | string | The generated execution prompt |
| `user` | string | Who logged the decision (`explain` only; from `AGENTROUTER_USER` or the OS username) |

Exit codes: `0` ok · `1` runtime · `2` bad usage/unknown id · `3` invalid
registry/config · `4` no eligible model.

---

## Mental model

```
your task ──▶ classify (7 dims) ──▶ hard filters ──▶ weighted scoring ──▶ recommendation + fallback
                                                                       ├─▶ execution prompt
                                                                       ├─▶ safety checklist (risk-gated)
                                                                       └─▶ SQLite log (explain/feedback)
```

The *logic* is stable; the *catalog* is your YAML. When the model landscape
shifts, edit the registry — never the code.
