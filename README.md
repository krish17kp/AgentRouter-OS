# AgentRouter OS

[![CI](https://github.com/krish17kp/AgentRouter-OS/actions/workflows/ci.yml/badge.svg)](https://github.com/krish17kp/AgentRouter-OS/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-0.4.0-brightgreen)

> **A CLI-first planner that reads your task and tells you which AI model, agent, IDE, or CLI tool to use — and why.**
>
> It classifies a task across 7 dimensions, scores every model in a YAML registry you control, and returns an explainable recommendation with a fallback, a risk-scaled safety checklist, and a logged, replayable decision. No cloud, no API keys required — everything lives locally in SQLite.

**Status: v0.4.0 — feature-complete (M1–M8).** 99 passing tests, 80%+ coverage enforced in CI, plus a post-build job that installs the real wheel and smoke-tests it.

**New in 0.4.0:** [per-user history & telemetry](#team-mode-shared-config--per-user-history), an [agent-host skill](#use-agentrouter-inside-claude-code-codex-antigravity-cursor) that plugs AgentRouter into Claude Code / Codex / Antigravity / Cursor, and a `--version` flag.

---

## Why AgentRouter

The model landscape changes every few weeks. AgentRouter is built on one assumption: **today's best model is soon obsolete.** So routing logic never hardcodes a model name — every decision is scored against a YAML registry you edit. Add tomorrow's model with a one-line YAML change, not a code change.

- **Explainable** — every recommendation logs its full score table; replay it anytime with `explain`.
- **Safe by default** — high-risk tasks always require human approval and are provably blocked from auto-execution.
- **Local-first** — routing needs no network and no keys; only live catalog refresh reaches out.
- **Token-saving** — inside an agent host, decompose a task and route each subtask to its cheapest adequate model.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/krish17kp/AgentRouter-OS.git
cd AgentRouter-OS

python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

pip install -e ".[dev]"
```

This installs the `agentrouter` command. (`python -m agentrouter` is equivalent everywhere below.)

```bash
agentrouter --version             # -> agentrouter-os 0.4.0
```

### 2. Initialize

```bash
agentrouter init                  # creates ~/.agentrouter/ with config + seed registries + DB
agentrouter registry list         # see the models you can route to
```

### 3. Route your first task

```bash
agentrouter route "Refactor the auth module to use JWT tokens"
```

Real output:

```text
Task: "Refactor the auth module to use JWT tokens"

How I read this task
  type: coding         complexity: medium   risk: high
  context: ~12000 tokens (medium)    output: code
  tools needed: file-edit
  approval: human-approval-required

Recommendation                                        score
  1  cursor/ide-coding-model                      0.95   <- recommended
  2  openrouter/strong-coding-model               0.94   <- fallback

Why: strongest weighted fit for coding (capability 0.9, cost-fit 0.8, context-fit 1.0);
ideal-use-case match; supports required tools: file-edit; capability weighted up (high complexity/risk).

Safety checklist (risk=high)
  [ ] Review full diff before applying
  [ ] Run the test suite
  [ ] Secret scan changed files
  [ ] Confirm rollback path
  [ ] Human sign-off (no auto-execute)

Decision logged: d_00001  (prompt saved with it; task text is stored locally)
Next: agentrouter explain d_00001   or   agentrouter prompt generate --from d_00001 --out prompt.md
```

Model names in the seed registry are **placeholders** — routing keys off the registry fields (capability, pricing, context window), never off a name. Point it at your real models by editing `~/.agentrouter/registry/models.yaml`.

---

## Common Tasks

### Override the classifier when it misreads the task

The classifier is keyword-based. When it guesses wrong, your flags win:

```bash
agentrouter route "tweak the thing" \
  --risk high \
  --tool file-edit,shell \
  --context-tokens 150000
```

Available overrides: `--risk {low|medium|high}`, `--tool <comma-separated>`, `--context-tokens <int>`. (There is no `--type` flag — task type is always inferred, then reflected in the score.)

### Replay a past decision

```bash
agentrouter explain d_00001
```

Shows the stored classification, **every excluded model with its reason**, the full per-model score table, any feedback-driven weight shifts, and the safety gate. Nothing is recomputed — it is an audit replay of what `route` decided.

### Generate a ready-to-paste prompt

```bash
# from a logged decision
agentrouter prompt generate --from d_00001 --out prompt.md

# or ad hoc for a specific tool
agentrouter prompt generate "write release notes" --tool openai/general-purpose-model
```

Paste the result into the recommended tool, or run it via `execute` (below).

### Give feedback so future routing improves

```bash
agentrouter feedback d_00001 --rating 2 --note "model struggled with the token limit"
```

`--rating` is an integer 1–5; `--note` is optional. Once 3+ ratings exist, each low rating (≤2) shifts a little weight from cost toward capability — bounded (step 0.01, cap +0.10, cost weight never below 0.05). The shift is recomputed from the feedback table on every route (no hidden state), shows up in the decision's `weight_shifts`, and reverts if you delete the feedback rows or set `learning: false` in `config.yaml`.

### Sync live model catalogs

```bash
agentrouter providers refresh openrouter --dry-run     # preview, write nothing
agentrouter providers refresh openrouter --limit 15    # import up to 15 models
agentrouter providers refresh openrouter --match claude # only ids containing "claude"

OPENAI_API_KEY=sk-... agentrouter providers refresh openai
```

Your hand-edited `models.yaml` **always wins** on collision. Generated entries land in `models.<provider>.generated.yaml` — delete that file to revert. OpenRouter's catalog endpoint is public (no key needed); if `OPENROUTER_API_KEY` is set it is sent as a header and never logged. Non-refreshable providers exit with code 2 and say so.

### Run the recommended tool (opt-in, risk-gated)

```bash
agentrouter execute d_00001          # shows what would run, asks for --yes
agentrouter execute d_00001 --yes    # actually runs it
```

Disabled everywhere by default. To opt a provider in, set `supports_execution: true` and an `exec_command` in `providers.yaml`. **Hard gate:** any decision with `risk=high` or non-auto approval is always blocked from auto-execution — the command tells you to run the prompt yourself.

### See telemetry and history

```bash
agentrouter stats                    # counts, risk/tier/user distributions, feedback
agentrouter stats --json             # same, machine-readable
agentrouter dashboard                # read-only local web page at http://127.0.0.1:8321/
```

### Get JSON for scripting

```bash
agentrouter route "summarize a 300k-token repository" --json
```

Emits a stable object: `decision_id`, `task`, `classification`, `weights`, `weight_shifts`, `excluded`, `scores` (each row carries `pricing_tier`), `recommendation`, `fallback`, `reason`, `gates`, and `prompt`. Full contract in [USER_GUIDE.md](USER_GUIDE.md).

---

## Use AgentRouter inside Claude Code, Codex, Antigravity, Cursor

The [`integrations/`](integrations/) directory turns AgentRouter into a **skill** any agent host can call, so the host routes its own subtasks to the cheapest adequate model and saves tokens.

**The division of labor:** the host agent (an LLM) decomposes a task into subtasks → AgentRouter (rule-based, auditable) routes each subtask to a pricing tier → the host maps that tier onto whatever models it actually has and runs each subtask there.

**Install into Claude Code:**

```bash
cp -r integrations/claude-code/agentrouter ~/.claude/skills/agentrouter   # all projects
# or:  cp -r integrations/claude-code/agentrouter .claude/skills/agentrouter   # this project
```

Then say *"route this task"* or *"use agentrouter in auto mode"* in any session.

**Other hosts (Codex, Antigravity, Cursor, custom):** paste [`integrations/AGENTS.md`](integrations/AGENTS.md) into the host's instruction file (`AGENTS.md`, `.cursorrules`, workspace rules, or a system prompt).

**Two modes:**

| Mode | Behavior |
| --- | --- |
| **manual** (default) | Recommend + explain. The user decides what runs where. |
| **auto** | Decompose → route each subtask → execute on the mapped host model (parallel subagents where supported). `risk=high` is **never** auto-executed. |

**Worked example (auto mode):** *"Research competitor API pricing and write a comparison doc"* →

```text
subtask 1  search the web for pricing pages       → low tier    → cheap/fast model
subtask 2  extract & normalize into a table       → medium tier → mid model
subtask 3  write the comparison document          → high tier   → strongest model
```

Three route calls, three decision ids, cheap work on cheap models. See [integrations/README.md](integrations/README.md) for per-host details.

---

## Understanding the Output

### Task classification (7 dimensions)

| Dimension | Values | Effect on routing |
| --- | --- | --- |
| **Type** | `coding`, `reasoning`, `writing`, `analysis`, `summarization`, `general` | Selects the capability blend used to score models |
| **Complexity** | `low`, `medium`, `high` | High shifts weight toward capability; low toward cost |
| **Risk** | `low`, `medium`, `high` | Sets the safety checklist; high forces human approval |
| **Context size** | token estimate → band `small`/`medium`/`large` | Models below the token count are filtered out; large shifts weight to context fit |
| **Output type** | `code`, `text`, `code+tests`, `data`, `plan` | Informs scoring |
| **Tool needs** | `file-edit`, `shell`, `web-search`, `vision`, … | Hard eligibility gate — missing a required tool excludes the model |
| **Approval level** | `auto`, `notify`, `human-approval-required` | Drives the execution gate |

### Scoring formula

Each eligible model gets a weighted score:

```text
score = w_cap·capability + w_cost·cost_fit + w_lat·latency_fit + w_ctx·context_fit
        + use_case_adjust − deprecation_penalty

default weights:  w_cap 0.45   w_cost 0.25   w_lat 0.15   w_ctx 0.15
```

Weights auto-shift with the task: high complexity/risk raises `w_cap`; a large context raises `w_ctx`. The top model is the recommendation; the runner-up (a different provider or cheaper tier where possible) is the fallback. Every term is logged so `explain` can show exactly why a model won.

---

## Configuration

All config lives in `~/.agentrouter/config.yaml` (override the whole directory with the `AGENTROUTER_HOME` env var).

```yaml
# Custom scoring weights (keys must be w_cap / w_cost / w_lat / w_ctx)
weights:
  w_cap: 0.55       # favor capability more
  w_cost: 0.15
  w_lat: 0.15
  w_ctx: 0.15

learning: true      # set false to freeze feedback-driven weight adaptation

policy:
  max_pricing_tier: medium   # routing never recommends above this tier
                             # valid tiers: free | low | medium | high | frontier
```

> Note: weight keys are `w_cap/w_cost/w_lat/w_ctx` and tiers are `free/low/medium/high/frontier`. Unknown weight keys are ignored; an invalid `max_pricing_tier` fails loudly with exit code 3.

### Add or retire a model

Edit `~/.agentrouter/registry/models.yaml` (schema in [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md)):

```yaml
models:
  - provider: anthropic
    model_id: claude-opus-4
    display_name: Claude Opus 4
    context_window: 200000
    max_output_tokens: 64000
    pricing_tier: frontier          # free | low | medium | high | frontier
    latency_tier: medium            # fast | medium | slow
    ability: { coding: 10, reasoning: 9, writing: 8 }   # each 0–10
    tool_support: [tool-use, file-edit, shell]
    vision_support: false
    ideal_use_cases: [coding, analysis]
    avoid_use_cases: []
    deprecation_status: active      # active | deprecated | retired
    fallback: [some-cheaper-model]
    source: manual
    last_updated: "2026-07-12"
```

To retire a model without deleting it, set `deprecation_status: retired` — it is filtered out of every recommendation. Changes apply on the next command; no restart, no code.

### Curate ability scores without touching generated files

Add `~/.agentrouter/registry/ability_overrides.yaml`:

```yaml
overrides:
  openrouter/anthropic/claude-x: { coding: 9, reasoning: 9 }
```

Overrides survive every `providers refresh`. Partial score maps are fine.

---

## Team Mode: shared config + per-user history

Point every teammate's `AGENTROUTER_HOME` at one shared directory to share the registry, config, and policy from a single source:

```bash
export AGENTROUTER_HOME=/shared/agentrouter      # setx on Windows
export AGENTROUTER_USER=alice                    # who this teammate is
```

- **`policy.max_pricing_tier`** in the shared `config.yaml` caps routing for everyone.
- **Per-user history (new in 0.4.0):** every decision records who made it — `AGENTROUTER_USER` if set, else the OS username. `stats` shows a `by_user` breakdown, the dashboard adds a per-user table and a user column, and `explain --json` includes the `user`.
- Databases created before 0.4.0 migrate automatically (old rows show as `unknown`).

This suits a small trusted team on a shared filesystem. Hosted multi-tenant deployment (auth, a server) is intentionally out of scope for a local-first CLI.

---

## Data & Privacy

Everything is local under `AGENTROUTER_HOME` (default `~/.agentrouter/`):

| Path | Contents |
| --- | --- |
| `config.yaml` | Scoring weights, learning toggle, team policy |
| `registry/models.yaml` | **The model catalog — edit to add/reprice/retire** |
| `registry/models.*.generated.yaml` | Written by `providers refresh`; safe to delete |
| `registry/ability_overrides.yaml` | Curated ability scores (survive re-refresh) |
| `registry/providers.yaml` | Provider definitions + opt-in execution config |
| `agentrouter.db` | SQLite decision + feedback log (task text, scores, users) |

- **Nothing leaves your machine** except explicit `providers refresh` fetches and tools you run with `execute --yes`.
- Task text is stored locally so `explain` can replay decisions. Use `--no-log` on `route` to skip persisting a sensitive task.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Registry file not found` | Run `agentrouter init` |
| `Registry error … (exit 3)` | The message names the bad YAML field — fix it, or `agentrouter init --force` to re-seed |
| `No eligible model (exit 4)` | Relax overrides: `--tool none`, raise `--context-tokens`, or add a capable model |
| `No decision found … (exit 2)` | Ids look like `d_00001`; run `agentrouter explain <id>` with a real id |
| `Execution blocked` | By design — high-risk never auto-executes. Enable low-risk via `supports_execution: true` + `exec_command` in `providers.yaml` |

### Exit codes

| Code | Meaning | Next step |
| --- | --- | --- |
| `0` | Success | Continue |
| `1` | Runtime error (network, file I/O) | Check the message; retry if transient |
| `2` | Bad usage or unknown decision id | Check syntax / id format |
| `3` | Registry or config invalid | Fix the named YAML field, or re-seed with `--force` |
| `4` | No eligible model | Relax constraints or add a model |

---

## Testing & Quality

```bash
pytest                                    # 99 tests, offline, ~8s
pytest --cov=agentrouter                  # coverage report (fails under 80%)
ruff check . && ruff format --check .     # lint + format
```

No test needs internet or an API key — provider-refresh tests mock the HTTP layer. CI runs the same suite on Python 3.11 / 3.12 / 3.13, then a **`build-smoke` job** builds the real sdist + wheel, installs the wheel into a clean venv, and smoke-tests the *installed* artifact (`--version` → `init` → `route --json` → `stats` → `registry list`). That catches packaging bugs — a missing seed file, a broken entrypoint — that editable installs never hit. See [TESTING.md](TESTING.md).

---

## Milestones

| # | Milestone | Status |
| --- | --- | --- |
| M1 | MVP routing engine (classify → recommend + fallback → prompt + checklist → log) | ✅ |
| M2 | Live catalog refresh + rich `explain` + `--json` | ✅ |
| M3 | Adapter expansion, staleness warnings, ability overrides | ✅ |
| M4 | Feedback learning loop (bounded weight adaptation) | ✅ |
| M5 | Read-only dashboard | ✅ |
| M6 | Gated execution (high-risk provably blocked) | ✅ |
| M7 | Teams & telemetry — shared config, policy, **per-user history** | ✅ |
| M8 | **Agent skill integration** (Claude Code / Codex / Antigravity / Cursor) | ✅ |

See [ROADMAP.md](ROADMAP.md) and [MILESTONES.md](MILESTONES.md) for the full breakdown, and [TODO.md](TODO.md) for honest remaining non-goals (hosted multi-tenant deployment, benchmark-based scoring).

---

## Docs & References

| Document | Purpose |
| --- | --- |
| [USER_GUIDE.md](USER_GUIDE.md) | Per-command walkthrough + JSON output contract |
| [integrations/README.md](integrations/README.md) | Install the skill into any agent host |
| [CLI_SPEC.md](CLI_SPEC.md) | Full command specification and flags |
| [ROUTING_RULES.md](ROUTING_RULES.md) | Scoring, classification, risk, fallback logic |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, request lifecycle, data flow |
| [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md) | Model entry schema (source of truth) |
| [PROVIDER_ADAPTER_SPEC.md](PROVIDER_ADAPTER_SPEC.md) | Provider adapter contract |
| [TESTING.md](TESTING.md) | Test layout, coverage, post-build verification |
| [SECURITY.md](SECURITY.md) | Secret handling, safety design, reporting |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, conventions, pre-push checklist |

---

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for setup, conventions, and pre-push checks.
