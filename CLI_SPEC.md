# AgentRouter OS — CLI Specification

> **Purpose:** Define every command, its arguments/flags, sample terminal I/O,
> and exit codes. The CLI (Typer) is a thin shell over the RoutingEngine
> ([ARCHITECTURE.md](ARCHITECTURE.md)). Command names here are canonical and
> match every other doc.
>
> Scope: `init`, `route`, `explain` (basic), `registry list`, `prompt generate`
> are **MVP**. `providers refresh` is **Capstone demo**. `feedback` is
> **Advanced**.

---

## 0. Global

- Binary: `agentrouter`
- Config + data home: `~/.agentrouter/`
  - `~/.agentrouter/config.yaml` — user settings (weights, default provider).
  - `~/.agentrouter/registry/models.yaml`, `providers.yaml` — the registries.
  - `~/.agentrouter/agentrouter.db` — SQLite decision + feedback log.
- Global flags: `--json` (machine output), `--config <path>`, `-v/--verbose`.

**Exit codes:** `0` success · `1` runtime error · `2` bad usage/args · `3`
registry validation failure · `4` no eligible model.

---

## 1. `init` — *MVP*

Scaffold `~/.agentrouter/` with default config and seed registries.

```
agentrouter init [--force]
```
- `--force` — overwrite existing config/registries.

```console
$ agentrouter init
Created ~/.agentrouter/config.yaml
Seeded registry/providers.yaml (6 providers)
Seeded registry/models.yaml (12 example models)
Initialized agentrouter.db
Ready. Try: agentrouter route "your task here"
```

---

## 2. `providers refresh` — *Capstone demo*

Call each provider adapter's `refresh_models` and rewrite the model registry.

```
agentrouter providers refresh [--provider <id>] [--dry-run]
```
- `--provider <id>` — refresh only one provider.
- `--dry-run` — show diffs, write nothing.

```console
$ agentrouter providers refresh
claude-code : 4 models (0 new, 1 updated)
openai      : 9 models (2 new, 0 deprecated)
openrouter  : 143 models (12 new, 3 retired)
cursor      : 3 models (config-only)
cli-agent   : 1 model (from config)
manual      : 1 model (static)
Registry updated. 156 active models.
```

---

## 3. `route "<task>"` — *MVP*

Classify a task and produce a recommendation + fallback + prompt + checklist,
and log the decision. This is the core command.

```
agentrouter route "<task>" [--context-tokens N] [--risk low|medium|high]
                            [--tool file-edit,shell] [--json] [--no-log]
```
- `--context-tokens N` — override estimated context size.
- `--risk` / `--tool` — override classifier inference.
- `--no-log` — don't persist (skips `decision_id`).

```console
$ agentrouter route "Refactor auth to use JWT rotation and add tests"

Classification
  task_type coding · complexity high · risk high · context medium(~12k)
  output code+tests · tools file-edit,shell · approval human-approval-required

Recommendation                                        score
  1  claude-code / <frontier-coding-model>            0.91   ← recommended
  2  cursor      / <strong-coding-model>              0.84   ← fallback

Safety checklist (risk=high)
  [ ] Review full diff before applying
  [ ] Run the test suite
  [ ] Secret scan changed files
  [ ] Confirm rollback path
  [ ] Human sign-off (no auto-execute)

Execution prompt saved. Decision id: d_00042
Next: agentrouter explain d_00042
```

Exit `4` if no model is eligible (recommends manual-agent, still logs).

---

## 4. `explain <decision_id>` — *MVP (basic) / Capstone (rich)*

Reconstruct a logged decision: classification, eligibility, full score table.

```
agentrouter explain <decision_id> [--json]
```

```console
$ agentrouter explain d_00042
Task: "Refactor auth to use JWT rotation and add tests"
Classification: coding/high/high/medium · tools[file-edit,shell]

Eligibility: 12 models → 5 eligible (7 excluded: 4 no file-edit, 3 context<12k)

Scores (top 5)
  model                                cap  cost  lat  ctx  adj   score
  <frontier-coding-model>              0.95 0.60 0.70 0.90 +0.05  0.91  ✔ recommended
  <strong-coding-model>                0.85 0.75 0.80 0.85 +0.05  0.84  ✔ fallback
  <mid-tier-coding-model>              0.70 0.90 0.90 0.80  0.00  0.78
  ...
Weights: cap .55 cost .15 lat .15 ctx .15 (shifted: complexity=high)
Gate: risk=high → human-approval-required, auto-execute blocked
```

---

## 5. `feedback <decision_id>` — *Advanced*

Record an outcome; the learning loop nudges weights.

```
agentrouter feedback <decision_id> --rating 1-5 [--accepted|--overrode <model>] [--note "..."]
```

```console
$ agentrouter feedback d_00042 --rating 5 --accepted --note "worked, tests passed"
Recorded. Acceptance rate: 83% (39/47). Weights nudged: w_cap +0.01
```

---

## 6. `registry list` — *MVP*

Print loaded models with key attributes.

```
agentrouter registry list [--provider <id>] [--active-only] [--json]
```

```console
$ agentrouter registry list --provider openrouter --active-only
PROVIDER    MODEL_ID                 CTX     PRICE     LAT   CODE/REAS/WRITE  TOOLS
openrouter  <mid-tier-coding-model>  128000  low       fast  7/7/7            tool-use,fn
openrouter  <cheap-fast-model>       32000   free      fast  5/6/6            fn
...
```

---

## 7. `prompt generate` — *MVP*

Generate (or regenerate) an execution prompt for a task or a logged decision,
without routing.

```
agentrouter prompt generate ["<task>" | --from <decision_id>] [--tool <id>] [--out <file>]
```

```console
$ agentrouter prompt generate --from d_00042 --out prompt.md
Wrote execution prompt for claude-code/<frontier-coding-model> → prompt.md
```

---

## 8. Command → tier summary

| Command | Tier |
|---|---|
| `init` | MVP |
| `route` | MVP |
| `explain` | MVP (basic), Capstone (rich table) |
| `registry list` | MVP |
| `prompt generate` | MVP |
| `providers refresh` | Capstone demo |
| `feedback` | Advanced |
