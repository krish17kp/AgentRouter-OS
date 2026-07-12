# Changelog

All notable changes to AgentRouter OS. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [Unreleased]

## [0.4.0] - 2026-07-12

### Added
- **Per-user history (M7 complete):** every logged decision records a user —
  `AGENTROUTER_USER` env var (shared-home teams) falling back to the OS
  username. `stats` gains a `by_user` distribution, the dashboard a per-user
  table + user column, `explain --json` a `user` field. Pre-0.4 databases
  migrate in place (old rows report `unknown`).
- **Agent skill integration (M8):** `integrations/` ships a portable Claude
  Code skill (`claude-code/agentrouter/SKILL.md`) and a host-agnostic
  `AGENTS.md` protocol snippet for Codex, Antigravity, Cursor, and any other
  agent host. Auto mode: the host agent decomposes a task into subtasks,
  routes each via `route --json`, maps the recommended pricing tier onto its
  own model lineup, and runs cheap subtasks on cheap models. Manual mode
  (default): recommend + explain only. High-risk subtasks are never
  auto-executed in any mode.
- **`pricing_tier` in `route --json`:** every score row (including
  `recommendation` and `fallback`) now carries the model's pricing tier — the
  field skill hosts map on.

## [0.3.0] - 2026-07-08

### Added
- **OpenAI refresh adapter (M3):** `providers refresh openai` fetches the models
  visible to your `OPENAI_API_KEY`; capability metadata from a static family
  table (the API exposes none); unknown families skipped with one aggregate warning
- **`--match` filter** on `providers refresh` (substring on model id)
- **Curated ability overrides (M3):** `registry/ability_overrides.yaml` overlays
  hand-curated scores on loaded entries without touching generated files
- **Registry staleness warnings (M3):** entries with `last_updated` older than
  90 days surface an aggregate warning at load time
- **Feedback learning loop (M4):** low ratings (≤2) shift weight from cost to
  capability — bounded (max +0.10), min-sample gated (3 ratings), recomputed
  deterministically from the feedback table so it is reversible by deleting
  feedback or setting `learning: false` in config.yaml; adaptations are logged
  in each decision's `weight_shifts`
- **Read-only dashboard (M5):** `agentrouter dashboard` serves a local
  stdlib-http page over the decision log (history, risk/tier distributions,
  feedback acceptance); GET-only by construction, no new dependencies
- **Gated execution (M6):** `agentrouter execute <id> --yes` runs the
  recommended tool via a provider `exec_command` argv template — opt-in per
  provider (`supports_execution: true`, ships false everywhere), high-risk /
  non-auto-approval decisions are provably blocked (NFR-8)
- **Telemetry + policy (M7-lite):** `agentrouter stats [--json]` aggregates
  decisions, risk/tier distributions, and feedback acceptance;
  `policy.max_pricing_tier` in config.yaml caps routing (team-enforceable via a
  shared `AGENTROUTER_HOME`)
- **PyPI release workflow:** `.github/workflows/release.yml` builds and
  publishes on GitHub Release via trusted publishing (needs one-time PyPI setup)
- Classifier fuzz tests (seeded, stdlib) and fallback-chain edge tests
  (46 → 94 tests, all offline)

## [0.2.0] - 2026-07-08

### Added
- **Live `providers refresh openrouter`** (Capstone M2): fetches the OpenRouter
  catalog into `registry/models.openrouter.generated.yaml`; manual registry
  always wins on collision; `--limit`, `--dry-run`; keyless operation
- GitHub Actions CI (Python 3.11/3.12/3.13): ruff lint + format check,
  pytest with 80% coverage gate, CLI entrypoint smoke check
- Dev tooling: ruff config, pytest-cov, `[dev]` extras in pyproject
- CLI smoke tests; contributor docs (CONTRIBUTING.md, TESTING.md, SECURITY.md,
  RELEASE.md)

### Changed
- Codebase formatted and linted with ruff (no behavior changes)
- pyproject.toml: full package metadata (license, classifiers, URLs)

## [0.1.0] - 2026-07-07

### Added
- Production-grade local CLI MVP: `init`, `route`, `explain`, `feedback`,
  `registry list`, `prompt generate`, `--json` output
- Rule-based 7-dimension task classifier with documentation-intent priority
  and CLI overrides
- Pydantic-validated YAML model/provider registries; hard eligibility filters
- Weighted scoring engine with recommendation + fallback and plain-English reason
- Risk-scaled safety gates; high-risk tasks require human approval
- SQLite decision log with replayable `explain`
- 46 offline tests; what/why/next error handling
