# AgentRouter OS

[![CI](https://github.com/krish17kp/AgentRouter-OS/actions/workflows/ci.yml/badge.svg)](https://github.com/krish17kp/AgentRouter-OS/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> **A CLI-first planner that reads your task and tells you which AI model, agent, IDE, or CLI tool to use — and why.**

**Status: production-grade local CLI, milestones M1–M6 implemented.** The CLI,
classifier, routing engine, safety gating, decision log, live catalog refresh
(OpenRouter + OpenAI), feedback learning loop, read-only dashboard, and opt-in
gated execution are implemented and tested (94 passing tests, 80%+ coverage
enforced in CI). Remaining honest gaps (benchmarked ability scores, PyPI
publication, multi-user team hosting) are listed in [TODO.md](TODO.md).

AgentRouter OS is a **routing brain, not an executor**. You describe a task; it
classifies the task across 7 dimensions, scores every model in a data-driven
YAML registry, and returns a recommendation with a fallback, a plain-English
reason, a ready-to-paste execution prompt, and a risk-scaled safety checklist.
Every decision is logged locally to SQLite and can be replayed with `explain`.

It is built around one hard assumption: **today's best model will be obsolete
soon.** No model name is hardcoded in logic. The catalog lives in editable
YAML — adding tomorrow's model is a config edit, not a code change.

---

## What is built (MVP)

- `route "<task>"` — classify → recommend + fallback + reason → prompt + safety checklist → log
- Rule-based task classifier (type, complexity, risk, context size, output, tool needs, approval level) with `--risk/--tool/--context-tokens` overrides
- Pydantic-validated YAML model + provider registries (malformed entries fail loudly)
- Hard eligibility filters: context window, required tools, vision, retirement
- Risk gating: high-risk tasks always require human approval, never auto-execute
- SQLite decision log; `explain <id>` reproduces any decision's full score table
- `registry list`, `prompt generate`, `feedback`, `--json` on route/explain
- **`providers refresh openrouter|openai` (M2/M3)** — live catalog sync into a
  separate `models.<provider>.generated.yaml`; manual registry always wins on
  collision; `--limit`, `--match`, `--dry-run`; OpenRouter works keyless,
  OpenAI needs a read-only `OPENAI_API_KEY`; delete the generated file to revert
- **Registry hygiene (M3)** — staleness warnings when `last_updated` is >90
  days old; `registry/ability_overrides.yaml` overlays curated scores on
  refreshed entries without hand-editing generated files
- **Feedback learning loop (M4)** — low ratings shift weight from cost toward
  capability, bounded and reversible (delete feedback or `learning: false`);
  every adaptation is logged in the decision's `weight_shifts`
- **`dashboard` (M5)** — read-only local web page over the decision log
  (history, risk/tier distributions, acceptance rate); stdlib only, GET-only
- **`execute <id> --yes` (M6)** — optionally runs the recommended tool via a
  provider `exec_command`; opt-in per provider (everything ships disabled) and
  high-risk decisions are provably blocked from auto-execution
- **`stats` + policy (M7-lite)** — local telemetry aggregates;
  `policy.max_pricing_tier` in config caps routing (share `AGENTROUTER_HOME`
  for a team-wide policy)

## What is NOT built (yet)

- Benchmarked ability scores — registry scores are hand-curated, pricing
  heuristics (refreshed), or your overrides; always advisory
- PyPI publication — the release workflow exists, but the one-time PyPI
  trusted-publisher setup hasn't been done (install is clone + `pip install -e .`)
- Hosted multi-user team mode — team policy works via a shared
  `AGENTROUTER_HOME`; there is no server, auth, or per-user accounts

---

## Quick start (fresh clone)

```console
# 0. Clone
git clone https://github.com/krish17kp/AgentRouter-OS.git
cd AgentRouter-OS

# 1. Virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux

# 2. Install (editable + dev tools: pytest, pytest-cov, ruff)
pip install -e ".[dev]"
# runtime only: pip install -e .

# 3. Verify
pytest                            # 94 tests, offline (refresh tests are mocked)
pytest --cov=agentrouter          # with coverage (80% gate)
ruff check . && ruff format --check .

# 4. Initialize (creates ~/.agentrouter/ with seed registries)
python -m agentrouter init

# 5. Look at what's routable
python -m agentrouter registry list

# 6. Route tasks
python -m agentrouter route "Polish the README for a Python CLI project"
python -m agentrouter route "Refactor authentication routes and migrate JWT token handling in production"
python -m agentrouter route "Summarize a 300k-token repository and generate an architecture report"

# 7. Replay a decision
python -m agentrouter explain d_00001
```

(`agentrouter <command>` works too after `pip install -e .`; `python -m agentrouter` needs no install step beyond requirements.)

### Example output

```console
$ agentrouter route "Refactor authentication routes and migrate JWT token handling in production"

How I read this task
  type: coding         complexity: high     risk: high
  context: ~12000 tokens (medium)    output: code+tests
  tools needed: file-edit
  approval: human-approval-required

Recommendation                                        score
  1  claude-code/frontier-coding-model            0.96   <- recommended
  2  openrouter/strong-coding-model               0.89   <- fallback

Why: strongest weighted fit for coding (capability 1.0, cost-fit 1.0, context-fit 0.6);
ideal-use-case match; supports required tools: file-edit; capability weighted up (high complexity/risk).

Safety checklist (risk=high)
  [ ] Review full diff before applying
  [ ] Run the test suite
  [ ] Secret scan changed files
  [ ] Confirm rollback path
  [ ] Human sign-off (no auto-execute)

Decision logged: d_00002  (prompt saved with it; task text is stored locally)
Next: agentrouter explain d_00002   or   agentrouter prompt generate --from d_00002 --out prompt.md
```

Full command reference: [USER_GUIDE.md](USER_GUIDE.md) · [CLI_SPEC.md](CLI_SPEC.md).

---

## Where your data lives

Everything is local, under one directory (override with `AGENTROUTER_HOME`):

| Path | Contents |
|---|---|
| `~/.agentrouter/config.yaml` | Scoring weights, `learning:` toggle, `policy:` caps |
| `~/.agentrouter/registry/models.yaml` | **The model catalog — edit this to add/reprice/retire models** |
| `~/.agentrouter/registry/models.*.generated.yaml` | Auto-generated by `providers refresh`; safe to delete |
| `~/.agentrouter/registry/ability_overrides.yaml` | Optional curated ability scores overlaid at load time |
| `~/.agentrouter/registry/providers.yaml` | Provider definitions (+ opt-in `exec_command` for `execute`) |
| `~/.agentrouter/agentrouter.db` | SQLite decision + feedback log |

**Privacy note:** `route` stores your task text verbatim in the local SQLite
log so `explain` can replay it. Nothing leaves your machine except the
catalog fetches you explicitly trigger with `providers refresh` (and any
command you explicitly run with `execute --yes`). For sensitive task text,
use `--no-log`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Registry file not found` | Run `agentrouter init` |
| `Registry error: ... invalid` (exit 3) | The error names the bad field; fix the YAML or re-seed with `agentrouter init --force` |
| `No eligible model` (exit 4) | Relax `--tool`/`--context-tokens` overrides or add a capable model to `models.yaml` |
| `No decision found with id ...` (exit 2) | Ids look like `d_00001`; the error lists recent valid ids |
| `providers refresh <p>` says not refreshable (exit 2) | Only `openrouter` and `openai` have live refresh; edit `models.yaml` for other providers |
| `Refresh failed: network error` (exit 1) | Check connectivity and retry; the registry was not modified, routing still works |
| Refreshed models look wrong | Scores are heuristics; add curated scores to `registry/ability_overrides.yaml` (survives re-refresh) |
| `Execution blocked` / `not enabled` (exit 2) | By design: high risk never auto-executes; low-risk execution needs `supports_execution: true` + `exec_command` in providers.yaml |
| Classifier got it wrong | Override: `--risk high`, `--tool file-edit,shell`, `--context-tokens 200000` |

Exit codes: `0` ok · `1` runtime · `2` bad usage/id · `3` registry/config invalid · `4` no eligible model.

---

## Limitations (read before trusting it)

- **Planner first.** Execution exists (M6) but is opt-in per provider and off everywhere by default; high risk never auto-executes.
- **Recommendations are advisory.** Scoring is a heuristic over registry metadata, not a live benchmark.
- **Registry accuracy = recommendation accuracy.** Stale YAML → stale advice; the loader now warns when entries age past 90 days.
- **Keyword classifier.** Ambiguous phrasing can misclassify; overrides exist and every decision is explainable.
- **Local-first.** No cloud, no accounts; team mode = a shared `AGENTROUTER_HOME` directory with one config/policy.

## Tech stack

Python 3.10+ · **Typer** (CLI) · **Pydantic v2** (registry + classification validation) · **YAML** (registries) · **SQLite** (decision log). No network dependencies in the MVP.

## Roadmap

M1 MVP ✅ → M2 live refresh ✅ → M3 adapter breadth + registry hygiene ✅ → M4 feedback learning ✅ → M5 read-only dashboard ✅ → M6 gated execution ✅ → M7 teams/telemetry (partial: stats + shared-home policy; hosted multi-user not built). Details: [ROADMAP.md](ROADMAP.md) · [MILESTONES.md](MILESTONES.md) · current gaps: [TODO.md](TODO.md).

## Document map

| Doc | Purpose |
|---|---|
| [USER_GUIDE.md](USER_GUIDE.md) | Per-command walkthrough + JSON output contract |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, pre-push checks, conventions |
| [TESTING.md](TESTING.md) | Test layout, coverage, live smoke test |
| [SECURITY.md](SECURITY.md) | Secret handling, safety design, reporting |
| [CHANGELOG.md](CHANGELOG.md) / [RELEASE.md](RELEASE.md) | Version history + release checklist |
| [TODO.md](TODO.md) | Completed work + honest remaining gaps |
| [PRD.md](PRD.md) / [BRD.md](BRD.md) | Product + business requirements |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components + request lifecycle |
| [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md) | Model-entry schema (source of truth) |
| [PROVIDER_ADAPTER_SPEC.md](PROVIDER_ADAPTER_SPEC.md) | Adapter contract (six providers) |
| [ROUTING_RULES.md](ROUTING_RULES.md) | Classification, scoring, risk, fallback |
| [CLI_SPEC.md](CLI_SPEC.md) | Command spec |
