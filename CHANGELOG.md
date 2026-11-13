# Changelog

All notable changes to AgentRouter OS. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [Unreleased]

### Changed
- Add an Axum local HTTP server slice with versioned service routes, canonical
  OpenAPI output, graceful shutdown, request IDs, optional API-key auth,
  explicit-origin CORS, and bounded rate/idempotency middleware. The Python API
  remains the release authority until full contract parity and all release
  gates pass.
- Share Rust rate-limit and idempotency primitives between the CLI and HTTP
  server, including a 16 MiB aggregate cached-response limit.
- Match FastAPI's field-level 422 messages for HTTP request validation and
  escape the OpenAPI title's em dash in the canonical JSON for cross-platform
  byte-stable serving.
- Run all TypeScript SDK operations against the Rust HTTP process as part of
  the Linux, Windows, and macOS Rust compatibility matrix.
- Add a Rust stdio MCP server for the Python server's five read-only and
  dry-run tools, with protocol/tool parity coverage, static JSON Schema
  contracts, and bounded newline-framed input. The Python CLI remains the
  supported entry point while Rust integration parity continues.
- Exercise the Python SDK against the Rust HTTP process for authenticated
  requests, routing, feedback, decision lookup, and dry-run responses.
- Add Rust provider-catalog conversion and bounded live refresh for OpenRouter
  and OpenAI, with Python/Rust comparisons for model records, price tiers,
  filtering, warnings, and catalog persistence. Redirects are disabled, API
  keys stay in request headers, response bodies are capped, and manual model
  registries remain untouched.
- Add a Rust reliability crate for bounded loopback load runs and soak reports,
  with Python/Rust checks for result summaries and request-ID handling. The
  Python server lifecycle and arbitrary request factory remain Python-owned.
- Port the legacy classifier and routing-gold evaluators, plus Markdown and CSV
  artifact writers, to the Rust evaluation crate. Full gold-set differential
  tests preserve the historical diagnostic scope; canonical release gates are
  unchanged.
- Add Rust `dataset` commands for blinded annotation packs, resumable human
  labeling, progress/export, disagreement-only adjudication, leakage-checked
  split builds, and development-set comparison. The command records only
  explicit human input and does not generate labels.
- Add a unified Rust `agentrouter` executable that dispatches migrated init,
  route, explain, feedback, prompt, registry, provider status, host/model
  inspection, doctor, dashboard, and dataset commands. Python CLI commands
  without Rust implementations remain explicit migration gaps.
- Connect the unified CLI to the Rust HTTP API server and stdio MCP server,
  preserving the local API's host/port controls, shared data home, inherited
  API-key settings, and MCP's standard input/output transport.
- Add a safety-gated Rust `execute` command for opted-in provider commands,
  local host commands, and the bounded OpenAI Responses API path. Stored gates
  are recomputed, high-risk decisions remain blocked, `--yes` is required, and
  `--dry-run` never executes. The Python reference now enforces that same
  dry-run guarantee for legacy provider commands.
- Extend the unified Rust CLI with local telemetry summaries and generated
  provider-catalog doctor, rollback, and restore operations. Rust/Python
  command checks cover saved feedback aggregates, reversible catalog changes,
  and corrupt-catalog reporting.
- Port the HTTP service business layer to `agentrouter-api` for model/host
  listing, classification, routing, decision lookup, feedback, and dry-run
  previews. It depends directly on routing, host, registry, classifier, and
  storage crates rather than the CLI; HTTP serving, middleware, and request
  lifecycle remain Python-owned.
- Extend `agentrouter-api` with typed and passthrough response models, plus
  Pydantic-compatible boolean and integer coercion for supported Rust ranges.
- Add an `agentrouter-api` Rust crate for classify, route, feedback and dry-run
  request validation, with Python/Rust checks for valid payloads, ignored extra
  fields, and field bounds.
- Make Rust classification deserialization reject unknown fields like the
  Python Pydantic schema, with a cross-language round-trip and rejection test.
- Add the Rust local-service SDK client for health, readiness, models, hosts,
  classification, routing, decision lookup, feedback and dry-run execution;
  request cleanup and structured API errors have offline HTTP fixture tests.
- Extend Rust catalog operations with provenance-aware status summaries,
  sorted generated-catalog listing, and guarded rollback/restore; Python/Rust
  differentials cover listing and rollback, while restore refuses linked files
  and concurrent destination replacement.
- Port deterministic annotation candidate generation and rules/learned/hybrid
  context-band comparison to Rust with Python differential coverage.
- Match Python text-file newline behavior on Windows for annotation artifacts.
- Match Python error and fallback behavior for malformed optional graph shapes.
- Port the annotation graph loader's bounded four-entry LRU cache semantics.
- Match Python contextual Unicode lowercase behavior for graph dependency IDs.
- Port the frozen context-band evaluation report, confidence intervals, seeded
  bootstrap, custom scoring, and prompt split-leak checks to Rust with exact
  Python/Rust report comparisons.
- Add Rust package contracts for evaluation, annotation constants, evaluator
  seed models, and the canonical distribution version; preserve empty package
  initializer exports where those Python packages intentionally expose none.
- Match Pydantic confidence, boolean, and manifest integer coercion in Rust
  annotation artifacts; remaining edge coercions stay explicitly Partial.
- Add a Rust offline evaluation runner for registered fixture profiles and
  single datasets, with deterministic sampling, provenance and dataset-quality
  reports, classification grading, and a composed seven-dimension `measure_all`
  scorecard. Real dataset downloads remain explicit external skips.
- Add the `agentrouter-evaluate` Rust command for dataset listing/validation,
  offline runs, Markdown reports, comparisons, availability status, explicit
  real-data preparation blockers, and context-band generalization.
- Tighten Rust annotation timestamp parsing to match the accepted Python
  datetime forms in differential fixtures and reject invalid separators.
- Match Python annotation datetime parsing for the underscore date/time
  separator, including omitted seconds, fractions, and timezone offsets.
- Match Pydantic integer coercion for underscore-separated and integral decimal
  strings in Rust annotation manifests.
- Match Python annotation datetime handling for rejected leap seconds, signed
  numeric timestamp strings, exponent forms, and microsecond rounding.
- Add Rust fixed-window rate limiting, TTL idempotency caching, and keyed
  single-flight primitives with Python contract checks.
- Extend Rust provider-catalog metadata parity for provenance, freshness fields,
  and report-only deprecation lists.
- Added Rust types and validation for the human annotation artifact schemas;
  supported datetime forms now normalize to Python-compatible ISO JSON while
  full scalar coercion and `fromisoformat` edge coverage remain open.
- Added the Rust repository-impact signal with offline differentials for graph
  nodes, edges, fallback behavior, and bounded feature values; malformed graph
  shape and Python cache semantics remain tracked parity work.
- Added Rust annotation pack ordering, resume filtering, progress, merging,
  disagreement-only adjudication packs, and CSV export with CPython-compatible
  seeded shuffling.
- Added Rust annotation artifact persistence for YAML candidates/datasets,
  JSONL labels, sorted JSON manifests, and Python-compatible canonical split
  hashes including Unicode.
- Added deterministic Rust candidate generation from the reviewed 63-prompt
  bank, matching Python seeded ordering, IDs, counts, source, and template.
- Ported deterministic annotation train/dev/private-holdout splits to Rust,
  including cluster preservation and a fail-closed frozen-holdout leakage check.
- Ported annotation duplicate and leakage guards to Rust, including Python
  sequence-matcher compatibility and deterministic split-safe clustering.
- Ported the human annotation merge/adjudication rules to Rust, preserving
  unresolved conflicts and explicit abstention without generating labels.
- Completed Rust evaluation-schema parity for serialized cases, normalized
  hashes, checksum copies, and invalid-input rejection.
- Completed Rust parity for evaluation provenance snapshots alongside the
  existing dataset-quality and leakage aggregation.
- Ported TwinRouterBench's dynamic-track offline status and actionable Docker
  run instructions to Rust, with Python/Rust differential coverage. Its static
  fixture contract continues to use the shared Rust evaluation adapter base.

### Added
- Rust evaluation parity now includes shared fixture-adapter behavior across six
  datasets and raw-row normalization for CLINC150, Banking77, MASSIVE, and
  LongBench v2, and SWE-bench; Rust now matches the complete LLMRouterBench
  adapter contract and offline run-status output. Remote dataset fetching
  remains external to the Rust adapter and is reported as such.
- **`agentrouter plugin doctor` now diagnoses instead of describing.** For every
  plugin destination it reports the state and the exact safe fix, with exit `0`
  installed and unmodified, `1` blocked, `2` needs attention, plus `--json`. It
  distinguishes an identical pre-existing copy (safe to adopt) from a different
  file at the same path, never suggests deleting an arbitrary directory, and
  never prints file contents. Plugin state also appears in unified
  `agentrouter doctor` as `plugins.state`, delegating to the plugin module rather
  than re-deriving its ownership rules.
- Rust migration probes for routing, registry validation, provider status, SQLite decision storage, and forced initialization. Python remains the shipping implementation until full contract parity and all release gates pass.
- Rust OpenAI Responses adapter slice with a rustls HTTPS transport, redirects disabled, bounded response reads, no automatic retries, and offline contract tests. It is not yet wired into a guarded Rust execution command.
- Dated routing benchmark report: 12/12 committed gold scenarios and 15 focused benchmark/invariant tests pass; live latency and cost remain unmeasured.
- macOS Python and Rust CI coverage now passes the configured platform jobs.
- Rust harness detection now matches the Python module's verified environment markers and conservative fallback behavior across eight differential cases.
- Rust now mirrors the dormant Python context-band model's deterministic features, artifact validation, and logistic inference, with 30 cross-language differential cases; classification remains rule-based and unchanged by default.
- The Rust diagnostics probe now writes an allowlisted redacted support bundle; including the SQLite log requires explicit opt-in and uses SQLite online backup. This remains a migration probe, not the shipped Python CLI.
- Diagnostic bundles now withhold all configured environment values except the resolved home path in both the Python implementation and Rust probe; user identifiers and configuration values are no longer copied into shareable artifacts.
- Added a release-mode Rust routing benchmark with the same synthetic fleet setup as the Python baseline; local paired results and limits are recorded in `docs/ROUTING_BENCHMARK_RESULTS_2026-11-11.md`.
- Rust `route_cli --verify-live` now has quota-aware one-step reranking with offline Python/Rust differential coverage; production live provider adapters remain unregistered.
- Rust doctor usage checks now reuse the shared host detector and bounded quota state machine instead of duplicating credential-variable checks; credentials and provider values remain withheld.
- Added a dedicated Rust `agentrouter-learning` crate for reversible feedback-weight adaptation, with nine Python/Rust differential cases and Python-compatible decimal rounding.
- Added a standalone Rust evaluation-metrics crate with offline Python/Rust report parity coverage for acceptable labels, tool sets, confusion matrices, high-risk recall, and per-case failures.
- Rust evaluation quality reporting now computes dataset label/provenance distributions, duplicate counts, and paraphrase-family split leakage from supplied case metadata; environment snapshots remain Python-only.
- Added Rust parity for evaluation's deterministic SHA-256 sampler, preserving seed/key ranking and original input order.
- Added a Rust normalized evaluation-case schema with matching defaults, enum values, nonempty-task validation at the fixture boundary, checksums, and Unicode-aware task hashing.
- Rust evaluation registry metadata now mirrors the eight dataset descriptors and five profile memberships; Python still constructs the actual dataset adapters.
- Rust now renders evaluation Markdown with an offline Python/Rust differential fixture; structured JSON, scorecard, and CSV file writes remain Python-only.
- Rust now computes the classification-only evaluation scorecard and its five release gates from measured metrics, with Python differential cases including the frozen context-band override.
- Rust now runs the evaluation safety score against its classifier, including gold high-risk semantics, proxy measurement labeling, human-approval gating, recall, and bounded failures.
- Rust now scores provider metadata completeness against the same six fields and placeholder values as Python; a differential fixture uses the packaged seed registry.
- Rust now runs the feedback-storage evaluation through an isolated SQLite home, checking decision save/load, feedback insertion, and aggregated stats against Python.
- Rust now evaluates routing against gold ability/provider/pricing/context constraints or the disclosed recommendation/fallback proxy, using its route implementation and supplied model registry.
- Rust now writes the full evaluation report directory: versioned result JSON, scorecard, Markdown, failure and holdout CSVs, and confusion matrices.
- Rust now scores the CLI platform evaluator from supplied command/group manifests; dynamic Typer registration discovery remains in Python.
- Rust now measures its classifier and router for supplied performance cases and mirrors the Python median, threshold decay, and report contract; seed loading and injected classifiers remain Python-side.
- Rust now loads evaluation result JSON, compares baseline/current scores and release gates, and writes matching Markdown/CSV comparison artifacts; Python comparison Markdown uses canonical LF across platforms.
- Rust now ports the AgentRouter gold adapter's metadata, availability, describe, load, checksum, and deterministic sample behavior; differential tests cover all 165 committed records plus Unicode/default handling.
- Rust evaluation now shares fixture-mode adapter loading, validation, checksums, deterministic sampling, metadata/availability descriptions, and explicit real-data skips across six external benchmark fixtures; live downloads and dataset-specific real transforms remain Python-only.
- Evaluation report text artifacts now use canonical LF line endings on all operating systems for byte-stable Python/Rust parity.
- Upgrade bundled SQLite to the patched 3.54.1 release and replace the unmaintained YAML parser with a pure-Rust serde-compatible layer; the Rust minimum is now 1.89.

### Fixed
- Evaluation `prepare --all` tests now use an offline mock and cannot download Hugging Face datasets during CI.
- Duplicate YAML keys are rejected by the Python registry loader, matching Rust fail-closed behavior.
- Website routing labels stay tied to the selected model across sorting; fallback provider text now reflects the actual pair.
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

- **Versioned HTTP API contract + compatibility gate** (`agentrouter contract export|check`):
  the REST surface is exported to a committed, byte-stable artifact at
  `contracts/http/v1/openapi.json` (provenance in a sibling `manifest.json`, so an
  unchanged API produces an unchanged file). A semantic checker classifies every
  difference as **breaking / risky / additive** and CI fails on breaking. Exit codes:
  `0` compatible, `1` breaking, `3` missing or untrustworthy baseline, `4` no
  `[server]` extra installed. A missing baseline is a failure, never a pass; export
  refuses to overwrite the baseline while a breaking change is present, and accepting
  one requires `--accept-breaking --reason` recorded in the manifest.
- **SDK capability manifest** (`contracts/sdk/capabilities.json`): both SDKs must
  *exercise* every operation they claim, against the real app — Python via in-process
  uvicorn, TypeScript via `scripts/serve_for_parity.py` over loopback.

### Changed
- **`/ready` reports `registry_unavailable` instead of `unavailable`** when the local
  registry is missing or malformed, matching what the `/v1` routes already returned for
  the same condition. **Breaking for any client branching on `code == "unavailable"`**
  for this case; neither SDK does — both pass `code` through opaquely. A new
  `internal_error` (500) code covers unexpected server-side faults. Both carry a fixed
  message on purpose: see the Security notes below.
- **Four previously untyped endpoints now declare their response shape**
  (`/v1/classify`, `/v1/route`, `/v1/decisions/{id}`, `/v1/execute/dry-run`). They were
  declared `-> dict`, so the exported contract said only "an object" and a renamed or
  removed field on them was undetectable. Nothing is stripped from the wire
  (`extra="allow"`), and the engine-owned payloads are typed `Any` rather than
  `dict`/`list` so a decision persisted by an older engine version still replays as 200
  instead of failing validation. Top-level key *order* changed on these four responses;
  JSON objects are unordered, but a snapshot-based consumer will see a diff.
- **Authentication is declared as an `APIKeyHeader` security scheme** rather than a bare
  header parameter, so adding or removing auth on an endpoint is visible in the contract.
  The wire protocol is unchanged: still `X-API-Key`.
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
- **An unknown plugin name was echoed back unbounded and unsanitised.** `get_plugin`
  interpolated the caller's string straight into its error, so a 5 KB argument
  produced a 5 KB message and embedded CR/LF forged extra lines in anything
  capturing CLI output — the same class of problem already fixed for the API's
  `decision_id`. Rather than keep two copies that could drift, the sanitiser now
  lives in `observability.safe_echo` (bounded to 64 characters, control/bidi
  ranges stripped) and both the installer and the HTTP surface call it.
- **That first sanitiser was itself incomplete.** Reviewing the fix found U+2028
  and U+2029 still passed through: neither is a control character, but
  `str.splitlines()` treats both as line boundaries, so a name containing one
  still forged a line — `agentrouter\u2028ERROR: your key is compromised` renders
  as two lines, the second looking like the program spoke. Both are now stripped,
  and the test derives the full boundary set from Python rather than trusting a
  hand-written range list, so the hole cannot quietly reopen.
- **A malformed registry no longer returns its own contents to the caller.** The
  `RegistryError` handler echoed `str(exc)`, which interpolates the registry path *and
  the offending YAML source line* — and a registry is malformed at exactly the moment
  somebody has pasted a credential into it, so this returned that credential to an
  **unauthenticated** caller on `/v1/models` and `/ready`. Both now answer a fixed
  message; run `agentrouter doctor` locally for the detail.
- **The same text is no longer written to the log on every request.** `/ready` is
  unauthenticated *and* rate-limit exempt, and an ERROR record reaches stderr even with
  no handler installed, so logging the exception let any caller write ~8 KB of registry
  content into the operator's log per request. Now ~200 bytes with no path and no
  content.
- **Unhandled server faults are typed and correlatable.** The `Exception` handler was
  registered on Starlette's outermost middleware, above the request-id middleware, so it
  never ran — faults were answered without an error envelope or `X-Request-ID`. They are
  now converted where the request id is still in scope, and logged at ERROR with a
  redacted traceback. **No raw traceback reaches an API client.**
- **Log redaction widened well beyond four vendor prefixes.** It previously missed
  Google, GitLab, Slack, HuggingFace, fine-grained GitHub PATs, AWS *temporary* keys,
  JWTs, connection-string passwords and generic `password=` pairs, and skipped non-string
  values entirely; redaction now also recurses into nested structures.
- **Echoed identifiers are bounded and sanitised.** A 5 KB `decision_id` produced a 5 KB
  error body, and CR/LF or a bidi override (U+202E) in one was reflected verbatim —
  usable for log forging and display spoofing.
- **The compatibility gate cannot be turned green by editing what it checks.** A baseline
  containing an unresolvable, self-referential or remote `$ref` is refused (such a ref
  inlines as `{}` and makes a schema look permissive); a baseline that exists but cannot
  be parsed is no longer treated as absent, which would have let corruption bypass the
  breaking-change refusal; export refuses to follow a symlink *or a hardlink* and to
  write outside the repo root; and CI additionally checks against the contract on the
  **base branch**, which the PR author does not control.
- **`$ref` expansion is bounded by one budget for the whole comparison**, not per call —
  a crafted fan-out document previously took 73 s from an 11 KB file and grew with the
  API. Bandit now also scans `scripts/`.
- Clarified that the app reads API keys from **shell environment variables** and
  does not auto-load `.env`; docs and the `.env` template updated to match.
- API-key checks now use `hmac.compare_digest` (constant-time) instead of `==`,
  closing a timing side-channel on `AGENTROUTER_API_KEY`.

### Fixed
- **`plugin list` and `plugin doctor` crashed on the state they exist to
  explain.** Both call `plugins.status()` to print a headline, and `status()`
  used `_safe_dest`, which correctly refuses a destination whose path contains a
  symlink or reparse point — but the refusal escaped, so both commands died with
  a raw traceback exactly when a user's plugin directory had been tampered with.
  `doctor --json` diagnosed the same state correctly throughout, which is what
  showed this was a display bug and not a missing diagnosis. `status()` now
  reports `blocked` (the word `diagnose` already uses) and never raises; the
  finding printed underneath names the path and the fix.
- **`USER_GUIDE.md` documented plugin commands that did not exist** — a `plugin
  status` subcommand, and `--apply` on both `install` and `uninstall` (install
  applies by default and takes `--dry-run`; uninstall takes no flags). Prose is
  never executed, so nothing failed until a reader typed it. The guide is
  corrected, and `tests/test_documented_commands.py` now parses the invocations
  out of the user-facing docs and checks each subcommand and flag against the
  real command tree, so a rename breaks the build instead of the reader.
- **A full disk during `plugin install` no longer produces a bare traceback.**
  Every other failure in the plugin installer raises a typed error with a
  remedy; a write failure escaped as a raw `OSError`, so the user got exit 1,
  empty output and a traceback in exactly the situation where one plain sentence
  helps most. It now reports the path and "check free space and that the
  directory is writable", while still cleaning up the partial staging file.
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
