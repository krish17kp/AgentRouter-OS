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

Paste the generated prompt into the recommended tool. AgentRouter never runs
it for you (planner, not executor — by design in v1).

## 6. `feedback <id>` — record the outcome

```console
$ agentrouter feedback d_00002 --rating 5 --note "worked, tests passed"
```

Stored in the local log today; weight adaptation ships in the Advanced tier.

## 7. `providers refresh` — live catalog sync (OpenRouter)

```console
$ agentrouter providers refresh openrouter --dry-run     # preview, write nothing
$ agentrouter providers refresh openrouter --limit 15    # import up to 15 models
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
- **Honesty note:** refreshed entries carry real context windows and pricing
  tiers, but `ability` scores are a pricing-based heuristic (marked in the
  entry's `notes`) — treat them as rougher than the curated manual entries.
- Other providers (`openai`, `claude-code`, …) are not refreshable yet; the
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
| `scores` | array | Ranked rows: `{model, provider, model_id, terms{cap,cost,lat,ctx,adj,dep}, score}` |
| `recommendation` | object \| null | Top-ranked score row |
| `fallback` | object \| null | Fallback score row |
| `manual_suggestion` | string \| null | Set when nothing was eligible |
| `reason` | string \| null | The one-line "Why" |
| `gates` | object | `{checklist: [...], auto_execute_allowed, approval_level}` |
| `prompt` | string | The generated execution prompt |

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
