# Changelog

All notable changes to AgentRouter OS. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [Unreleased]

### Added
- **Local REST API** (`agentrouter server`, `[server]` extra): classify/route/
  explain plus a dry-run-only execute preview. No remote execution.
- **MCP server** (`agentrouter mcp`, `[mcp]` extra): read-only route/classify/
  explain/list tools over stdio; deliberately no execute tool.
- **Plugin install/uninstall/doctor** for the Claude Code and Codex agent skills.
- **Graded evaluation** (`agentrouter eval run --all`) over a gold benchmark plus
  public-benchmark fixtures, with release gates.
- **Route-control flags** on `route`: `--max-price`, `--stable-only`,
  `--available-only`, `--prohibit-tool`, `--uncertainty-threshold`.
- **Frozen context-band generalization evaluation** with separate development/final splits,
  checksum and leakage locks, macro-F1/recall/confidence intervals, immutable historical
  comparison, canonical CI enforcement, and held-out failure artifacts.
- **Bounded Linux mutation workflow** using pinned mutmut 3.6.0, critical-module score gates,
  explicit tool-failure reporting, survivor review, timeouts, and uploaded evidence.
- **Trusted catalogs** (`agentrouter providers status/rollback/restore/doctor`): every
  `providers refresh` catalog now carries a structured `provenance` block (source URL, UTC
  fetch time, count, tool version, CLI args) and is written atomically; `status` reports
  age/freshness and provenance offline; `rollback` safely reverts a generated catalog with
  rotating backups, `restore` reverses a rollback, and `doctor` validates every generated
  catalog and exits non-zero only on real corruption. Refreshing a provider with an existing
  generated catalog reports candidate deprecations (report-only, never auto-deleted).
- **Verified execution-host states** (`agentrouter hosts doctor/list/show`): every host now
  reports a precise readiness state — `missing`, `installed`, `configured`, `authenticated`,
  `authorized` or `degraded` — with a concrete next step, instead of only
  available/unavailable/unknown. Detection stays offline and read-only: it checks whether a
  binary is on PATH and whether a credential/config path or env var *exists*, never opening a
  credential file, printing a key, or making a network call. `authorized` requires an opt-in
  live check and is never inferred from local evidence. `hosts doctor` now ends with the
  closest concrete fix and exits non-zero only when no real host is ready.
- **CI release-gate semantics:** the release-readiness check is now split into a non-enforcing
  `release-readiness-report` (every push/PR, always green, reports the honest YES/NO) and
  `enforce-release-gate` (RC-to-main PRs, release tags, or explicit dispatch only, full
  enforcement, no lowered thresholds).

### Changed
- **Python support clarified:** the minimum supported Python remains **3.10**
  (`pyproject.toml` `requires-python = ">=3.10"`), and CI verifies every supported
  version — **3.10 / 3.11 / 3.12 / 3.13**. (A prior draft of this entry incorrectly
  claimed the floor had been raised to 3.11; pyproject and the CI matrix never
  dropped 3.10, so the floor is reconciled back to 3.10.)
- **Context-band routing:** the classifier's inferred `context_tokens` now feeds
  model eligibility and scoring (not just the displayed context band), so the
  recommended model may change for context-sensitive tasks. Output shape is
  unchanged and the behavior is eval-gated (`context_band_accuracy`).
- **Canonical readiness is held by the frozen context holdout:** the final accuracy is 0.5778
  after a development-only generalization revision, below the unchanged 0.90 gate. The other six
  gates pass; a valid lower result is reported instead of preserving the previous in-sample claim.

### Security
- Clarified that the app reads API keys from **shell environment variables** and
  does not auto-load `.env`; docs and the `.env` template updated to match.
- API-key checks now use `hmac.compare_digest` (constant-time) instead of `==`,
  closing a timing side-channel on `AGENTROUTER_API_KEY`.

### Fixed
- **A blank API key no longer reports a host as available.** Host detection tested the env var
  for truthiness, so `OPENAI_API_KEY="   "` (set but empty/whitespace) counted as available and
  `execute` would target a host that cannot possibly authenticate. Such a value now reports
  `degraded` / unavailable with a fix-it message.
- Plugin install/uninstall now persists exact ownership and installed digests, journals forced
  replacements for crash recovery, preserves backup identity/metadata, rejects traversal,
  link/reparse, hard-link, and portable special-name hazards, preserves concurrent edits, migrates
  historical registry paths, and removes only an empty integration directory it created. The
  explicit `--adopt-identical` flag supports pre-manifest legacy installs.
- **Packaging:** the gold benchmark and evaluation fixtures now ship inside the
  package (`agentrouter/benchmarks/`, `agentrouter/evaluation/fixtures/`) and load
  via `importlib.resources`, so `agentrouter eval run` / `evaluate` work from a
  real `pip install` (previously they only resolved in a source checkout).
- `init --force` now backs up an existing `models.yaml` / `providers.yaml` /
  `config.yaml` to a `.bak` sibling before reseeding, so a hand-edited catalog
  is no longer silently destroyed on re-init.
- `--prohibit-tool` now rejects an unknown tool name (with a "did you mean …?"
  hint) instead of silently dropping nothing.
- `--help` for `server` / `mcp` renders the extras command correctly
  (`pip install "agentrouter-os[server]"`) instead of swallowing `[server]`.
- Replaced em-dashes in printed CLI strings and command `--help` text with ASCII
  `-` so stock Windows consoles (cp437/cp1252) no longer show a mojibake character.
- The `setup` "no host available yet" hint now fires correctly: it counts only
  real execution hosts, since the always-available `manual` host previously
  suppressed the warning on every machine.
- `agentrouter.__version__` is sourced from installed metadata (was pinned at a
  stale `0.1.0`); it now matches the packaged version.

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
- **`--version` flag** on the CLI.
- **Post-build verification in CI:** new `build-smoke` job builds the sdist +
  wheel, installs the wheel into a clean venv, and smoke-tests the installed
  artifact (`--version`, `init`, `route --json`, `stats`, `registry list`) —
  catches packaging bugs editable installs never hit.

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
