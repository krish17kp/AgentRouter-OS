# AgentRouter OS

[![CI](https://github.com/krish17kp/AgentRouter-OS/actions/workflows/ci.yml/badge.svg)](https://github.com/krish17kp/AgentRouter-OS/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> **A CLI-first planner that reads your task and tells you which AI model, agent, IDE, or CLI tool to use — and why.**
> Classify tasks across 7 dimensions, score every model in your YAML registry, and get explainable recommendations with safety checklists and execution logs. Built for teams: no cloud, no API keys required, everything stored locally in SQLite.

**Status: Production-grade v0.3.0** — All core features implemented and tested. 94 passing tests, 80%+ coverage enforced in CI.

---

## Quick Start

### 1. Install

```console
# Clone the repository
git clone https://github.com/krish17kp/AgentRouter-OS.git
cd AgentRouter-OS

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux

# Install with development tools
pip install -e ".[dev]"
```

### 2. Initialize

```console
# Initialize AgentRouter (creates ~/.agentrouter/ with seed registries)
python -m agentrouter init

# View available models
python -m agentrouter registry list
```

### 3. Route Your First Task

```console
# Route a task to get a recommendation
python -m agentrouter route "Polish the README for a Python CLI project"
```

**Example output:**

```
How I read this task
  type: coding         complexity: medium    risk: low
  context: ~2000 tokens          output: text
  tools needed: none
  approval: human-review

Recommendation                                        score
  1  claude-code/frontier-coding-model            0.94   <- recommended
  2  openrouter/capable-coding-model              0.87   <- fallback

Why: strongest weighted fit for coding (capability 1.0, cost-fit 0.95, context-fit 1.0);
ideal-use-case match; context-aware capability weighting.

Safety checklist (risk=low)
  [ ] Review output quality
  [ ] Check for hallucinations
  [ ] Verify sources if applicable

Decision logged: d_00001
Next: agentrouter explain d_00001   or   agentrouter prompt generate --from d_00001
```

---

## Common Tasks

### Route a Complex Task with Full Context

```console
# Route a high-risk production task
python -m agentrouter route \
  "Refactor authentication and migrate JWT token handling in production" \
  --risk high \
  --tool file-edit,shell \
  --context-tokens 50000

# Output shows:
# - Task classification (type, complexity, risk level)
# - Top 2 recommendations with scores
# - Plain-English reasoning
# - Risk-appropriate safety checklist
# - Decision ID for future reference
```

### Override the Classifier

```console
# If the classifier gets the task type wrong, override it
python -m agentrouter route "Generate an image" \
  --type creative \
  --risk medium

# Use flags to fine-tune classification:
# --risk low|medium|high
# --tool none|file-edit|shell|web-search|etc
# --context-tokens <number>
```

### View Routing Decision History

```console
# List recent decisions
python -m agentrouter explain d_00001

# Output shows:
# - Full task text
# - Classification breakdown
# - Complete scoring table for all eligible models
# - Final recommendation with fallback
# - Any applied feedback weights
```

### Generate a Ready-to-Use Prompt

```console
# Extract the routing decision as a standalone prompt
python -m agentrouter prompt generate --from d_00001 --out prompt.md

# The generated prompt includes:
# - Full task context
# - Recommended model
# - Role and instructions
# - Output expectations
# - Ready to copy/paste into your editor
```

### Refresh the Model Catalog from Live Providers

```console
# Sync models from OpenRouter (works without API key)
python -m agentrouter providers refresh openrouter

# Sync from OpenAI (requires read-only OPENAI_API_KEY)
python -m agentrouter providers refresh openai \
  --match "gpt-4" \
  --limit 10

# Preview changes without modifying registry
python -m agentrouter providers refresh openrouter --dry-run

# Auto-generated files are in ~/.agentrouter/registry/models.*.generated.yaml
# Delete them anytime to revert to manual registry
```

### Log Feedback and Improve Future Decisions

```console
# Rate a past routing decision (improves future similar tasks)
python -m agentrouter feedback d_00001 \
  --rating unsatisfactory \
  --reason "Model struggled with token limits"

# Feedback shifts weights toward capability over cost
# View how feedback changed scoring:
python -m agentrouter explain d_00001

# All weight shifts are logged in the decision's weight_shifts field
# Disable learning: set learning: false in ~/.agentrouter/config.yaml
```

### Execute a Routing Decision

```console
# Run the recommended tool directly (opt-in, gated by risk)
python -m agentrouter execute d_00001 --yes

# High-risk decisions are BLOCKED from auto-execution (by design)
# Low-risk execution requires explicit provider config:
# - Set supports_execution: true in providers.yaml
# - Define exec_command for the tool
# - Execution never happens without --yes flag
```

### View Decision History and Stats

```console
# Open interactive dashboard (local web page)
python -m agentrouter dashboard

# Shows:
# - Decision history (tasks, recommendations, times)
# - Risk tier distribution chart
# - Model usage statistics
# - Acceptance rate trends
# - All data from local SQLite log
```

### Check Team Policies and Limits

```console
# View current policy configuration
cat ~/.agentrouter/config.yaml

# Example config with team policy:
# learning: true
# weights:
#   capability: 0.5
#   cost_fit: 0.3
#   context_fit: 0.2
# policy:
#   max_pricing_tier: standard    # Enforce cost limits across team
```

---

## Understanding the Output

### Task Classification (How I Read This)

AgentRouter classifies your task across 7 dimensions:

| Dimension          | Values                                                              | Effect                                                                      |
| ------------------ | ------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Type**           | coding, research, creative, operations, analysis, learning, unknown | Filtered against model capabilities                                         |
| **Complexity**     | low, medium, high, extreme                                          | Weights toward capability (high complexity = more capable models preferred) |
| **Risk**           | low, medium, high                                                   | Determines safety checklist; high-risk blocks auto-execution                |
| **Context Size**   | (tokens)                                                            | Models must have sufficient context window                                  |
| **Output Type**    | text, code, code+tests, structured-data, unknown                    | Capability filter                                                           |
| **Tool Needs**     | none, file-edit, shell, web-search, vision, etc                     | Hard eligibility gate                                                       |
| **Approval Level** | none, human-review, human-approval-required                         | Determines execution gating                                                 |

Override any classification with CLI flags:

```console
python -m agentrouter route "<task>" \
  --type coding \
  --risk high \
  --tool file-edit,shell \
  --context-tokens 200000
```

### Scoring and Recommendations

Each eligible model is scored across three dimensions (weighted sum):

```
score = (capability × C) + (cost_fit × H) + (context_fit × X)

Where:
  C = capability weight (default 0.5, increased for high complexity)
  H = cost_fit weight (default 0.3)
  X = context_fit weight (default 0.2)
```

**Top 2 models are returned:**

1. **Primary recommendation** (highest score)
2. **Fallback** (second highest, different provider preferred)

Both scores and reasoning are logged for explainability.

---

## Data and Privacy

### Where Your Data Lives

Everything is local under one directory (customize with `AGENTROUTER_HOME`):

| Path                                              | Contents                                                        |
| ------------------------------------------------- | --------------------------------------------------------------- |
| `~/.agentrouter/config.yaml`                      | Scoring weights, learning toggle, team policy limits            |
| `~/.agentrouter/registry/models.yaml`             | **The model catalog — edit to add/reprice/retire models**       |
| `~/.agentrouter/registry/models.*.generated.yaml` | Auto-generated by `providers refresh`; safe to delete           |
| `~/.agentrouter/registry/ability_overrides.yaml`  | Curated ability scores (survives re-refresh)                    |
| `~/.agentrouter/registry/providers.yaml`          | Provider definitions + opt-in execution config                  |
| `~/.agentrouter/agentrouter.db`                   | SQLite decision + feedback log (all task text, scores, outputs) |

### Privacy Notes

- **Nothing leaves your machine** except explicit catalog fetches (`providers refresh`) and tools you explicitly execute (`execute --yes`)
- **Task text is stored locally** in SQLite so `explain` can replay full decisions
- Use `--no-log` to skip logging a sensitive task
- Share `AGENTROUTER_HOME` across a team for unified policy (same config, shared decision log)

---

## Troubleshooting

### Common Issues and Solutions

```console
# Registry file not found
>> Fix: Run agentrouter init

# Registry error: ... invalid (exit 3)
>> Fix: The error names the bad YAML field. Either fix it or:
python -m agentrouter init --force

# No eligible model found (exit 4)
>> Fix: Relax overrides or add capable models:
python -m agentrouter route "<task>" --tool none --context-tokens 500000

# No decision found with id ... (exit 2)
>> Fix: Ids look like d_00001. Run explain without args to list recent:
python -m agentrouter explain

# Execution blocked / not enabled (exit 2)
>> Fix: By design. High-risk decisions never auto-execute.
>> Enable for low-risk: set supports_execution: true + exec_command in providers.yaml
```

### Exit Codes

| Code | Meaning                           | Next Step                                  |
| ---- | --------------------------------- | ------------------------------------------ |
| `0`  | Success                           | Continue                                   |
| `1`  | Runtime error (network, file I/O) | Check error message; retry if temporary    |
| `2`  | Bad usage or invalid ID           | Check command syntax or decision ID format |
| `3`  | Registry or config invalid        | Fix YAML or re-seed with `--force`         |
| `4`  | No eligible model found           | Relax constraints or add models            |

---

## Features

### Core Routing Engine

- **Task classification** across 7 dimensions (type, complexity, risk, context, output, tools, approval)
- **Pydantic-validated registries** — malformed entries fail loudly with clear errors
- **Scoring over YAML** — no hardcoded model names, config-driven recommendations
- **Hard eligibility filters** — context window, required tools, vision capability, retirement status
- **Risk gating** — high-risk tasks always require human approval, never auto-execute

### Decision Logging & Explainability

- **SQLite decision log** — every routing decision is stored locally
- **Full replay with `explain <id>`** — re-run any decision and see the complete score table
- **Feedback learning loop** — rate decisions to improve similar future tasks
- **Weight adaptation log** — track how feedback shifts scoring over time

### Live Model Catalog Management

- **`providers refresh openrouter|openai`** — sync live model catalogs into generated YAML files
- **Manual registry always wins** — hand-edited models override generated ones on collision
- **Registry hygiene warnings** — staleness alerts when entries age >90 days
- **Curated ability overlays** — `ability_overrides.yaml` applies expert scores without re-editing generated files

### Dashboard & Analytics

- **Read-only decision dashboard** — interactive web page over the decision log
- **Usage statistics** — model adoption, risk distribution, decision trends
- **Decision replay** — relive any past routing decision with full context
- **Acceptance rate tracking** — monitor decision quality over time

### Gated Execution

- **`execute <id> --yes`** — optionally run the recommended tool from the CLI
- **Opt-in per provider** — execution is off by default everywhere
- **Risk-scaled blocking** — high-risk decisions are provably prevented from auto-execution
- **Custom exec_commands** — define how each provider executes via YAML

### Team Mode

- **Shared home directory** — point `AGENTROUTER_HOME` to a shared location for unified policy
- **Team-wide policy enforcement** — `policy.max_pricing_tier` caps routing across the team
- **Unified decision log** — see team decision history and aggregate stats
- **No auth or cloud** — works entirely offline with a shared filesystem

---

## Model Registry and Configuration

### Adding a New Model

Edit `~/.agentrouter/registry/models.yaml`:

```yaml
- model: claude-opus-4
  provider: anthropic
  pricing_tier: premium
  capability_score: 0.95
  supports:
    - coding
    - research
    - creative
    - analysis
  max_tokens: 200000
  vision: false
  retirement_date: null
  last_updated: 2026-01-15
```

### Curating Ability Scores

Add expert overrides to `~/.agentrouter/registry/ability_overrides.yaml`:

```yaml
overrides:
  - model: gpt-4-turbo
    type: coding
    score: 0.88
  - model: claude-3-sonnet
    type: research
    score: 0.92
```

These persist across re-refreshes from live providers.

### Disabling a Model

Set `retirement_date` in the model entry:

```yaml
retirement_date: "2026-03-01" # Model will no longer be recommended
```

---

## Advanced Usage

### Batch Routing Multiple Tasks

```console
# Create a file with tasks (one per line)
cat > tasks.txt << 'EOF'
Refactor authentication flow
Optimize database query
Write unit tests for auth module
EOF

# Route each task
while IFS= read -r task; do
  python -m agentrouter route "$task"
done < tasks.txt
```

### JSON Output for Integration

```console
# Get structured output for programmatic use
python -m agentrouter route "My task" --json

# Output:
# {
#   "decision_id": "d_00042",
#   "task": "My task",
#   "classification": {
#     "type": "coding",
#     "complexity": "high",
#     "risk": "medium",
#     ...
#   },
#   "recommendation": {
#     "rank": 1,
#     "model": "claude-code/frontier",
#     "score": 0.94
#   },
#   "fallback": {
#     "rank": 2,
#     "model": "openrouter/strong",
#     "score": 0.87
#   },
#   ...
# }
```

### Custom Weights for Your Team

Adjust `~/.agentrouter/config.yaml`:

```yaml
weights:
  capability: 0.6 # Favor capable models more
  cost_fit: 0.2 # Reduce cost sensitivity
  context_fit: 0.2

learning: false # Disable feedback learning if not wanted

policy:
  max_pricing_tier: premium # Team-wide cost cap
```

---

## Architecture & Design

AgentRouter is built around one hard assumption: **today's best model will be obsolete soon.**

- **No hardcoded model names** in logic — all decisions reference the YAML registry
- **Config-driven scoring** — add tomorrow's model with a YAML edit, not a code change
- **Reversible decisions** — delete generated files or feedback logs to revert changes
- **Local-first** — no cloud dependencies, no network required for routing (only for catalog refresh)
- **Explainable by design** — every decision is loggable, replayable, and auditable

---

## Testing & Quality

- **94 passing tests** — full test coverage across classifier, scorer, loader, and CLI
- **80%+ code coverage enforced** in CI
- **Offline test suite** — `providers refresh` tests are mocked, no network required
- **Ruff formatting** — consistent code style

Run tests locally:

```console
pytest                            # Run all tests
pytest --cov=agentrouter          # With coverage report (80% gate)
ruff check . && ruff format --check .  # Lint and format check
```

---

## What's Next

**Completed (M1–M6):**

- ✅ MVP routing engine
- ✅ Live provider refresh (OpenRouter, OpenAI)
- ✅ Registry hygiene + ability overrides
- ✅ Feedback learning loop
- ✅ Read-only dashboard
- ✅ Gated execution

**In Progress (M7):**

- 📋 Benchmarked ability scores
- 📋 PyPI publication
- 📋 Multi-user team hosting

See [ROADMAP.md](ROADMAP.md) for full details and [TODO.md](TODO.md) for honest remaining gaps.

---

## Docs & References

| Document                                             | Purpose                                        |
| ---------------------------------------------------- | ---------------------------------------------- |
| [USER_GUIDE.md](USER_GUIDE.md)                       | Per-command walkthrough + JSON output contract |
| [CLI_SPEC.md](CLI_SPEC.md)                           | Full command specification and flags           |
| [ROUTING_RULES.md](ROUTING_RULES.md)                 | Scoring logic, classification, risk, fallback  |
| [ARCHITECTURE.md](ARCHITECTURE.md)                   | Components, request lifecycle, data flow       |
| [MODEL_REGISTRY_SCHEMA.md](MODEL_REGISTRY_SCHEMA.md) | Model entry schema (source of truth)           |
| [PROVIDER_ADAPTER_SPEC.md](PROVIDER_ADAPTER_SPEC.md) | Provider adapter contract (6 providers)        |
| [CONTRIBUTING.md](CONTRIBUTING.md)                   | Dev setup, conventions, pre-push checklist     |
| [TESTING.md](TESTING.md)                             | Test layout, coverage targets, live test       |
| [SECURITY.md](SECURITY.md)                           | Secret handling, safety design, reporting      |
| [CHANGELOG.md](CHANGELOG.md)                         | Version history and release notes              |
| [MILESTONES.md](MILESTONES.md)                       | Milestone breakdown (M1–M7)                    |
| [TODO.md](TODO.md)                                   | Completed work + honest remaining gaps         |

---

## License

MIT — see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, conventions, and pre-push checks.
