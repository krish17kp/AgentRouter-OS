# AgentRouter OS — TODO / Status

> Updated at the end of Capstone M2 (2026-07-07). Honest status:
> **production-grade local MVP + live OpenRouter refresh** — not fully
> production-ready; gaps listed below.

## ✅ Completed in Capstone M2 (live providers refresh)

- [x] **OpenRouter adapter** (`agentrouter/refresh.py`, stdlib `urllib` — no new
      dependencies): fetches the live catalog, maps entries to the registry
      schema (context window, max output, pricing tier from per-token price,
      tool support, vision), fail-loud on unmappable entries.
- [x] **Real `providers refresh openrouter` command** with `--limit`,
      `--dry-run`, clear what/why/next errors for network failure, invalid
      response shape, unsupported provider, and missing registry dir.
- [x] **Generated-registry storage:** writes
      `registry/models.openrouter.generated.yaml` (idempotent overwrite, header
      warns against hand-edits). Manual `models.yaml` is never touched, always
      wins on key collision, and deleting the generated file reverts cleanly.
- [x] **19 mocked-HTTP tests** (`tests/test_refresh.py`) — pricing-tier mapping,
      entry mapping, skip-with-warning, limit, bad shape, dry-run, network-error
      exit code, unsupported provider, manual-wins collision, idempotency,
      key-never-printed, works-without-key. pytest needs no network and no key
      (27 → 46 tests, all passing).
- [x] **Live smoke test performed** against the real endpoint (15 models
      imported, merged into `registry list`, routing verified).
- [x] Docs updated: README (built list, storage table, troubleshooting),
      USER_GUIDE §7 (usage + live smoke instructions).

**Test-key note:** the OpenRouter `/models` catalog endpoint is public, so the
provided test key was **not needed** — live verification ran keyless. If
`OPENROUTER_API_KEY` is set it is sent as an auth header only, never printed or
logged (covered by a test). ⚠️ The example key currently sits in the tracked
`.env.example` — it should be rotated and replaced with a blank placeholder.

**M2 known limits (by design):** refreshed `ability` scores are a pricing-based
heuristic (marked in each entry's `notes`); `latency_tier` defaults to medium
(the API exposes no latency data); import order is the API's (newest first),
capped by `--limit`.

## ✅ Completed in this hardening pass

- [x] **Classifier fix:** documentation intent (README, docs, PRD, BRD, roadmap,
      milestones, user guide, overview, report, rewrite/polish/explain) is now
      checked *before* coding keywords — "Python/CLI/repo/project" mentions no
      longer force coding. "docstring" explicitly stays coding.
- [x] **Regression tests:** all required example tasks (README polish/rewrite,
      PRD/BRD, architecture docs, roadmap/milestones, Typer CLI coding,
      high-risk auth/production, long-context summarization) + error-path tests
      (13 → 27 tests, all passing).
- [x] **CLI UX:** route now echoes the original task, "How I read this task"
      classification block, one-line plain-English **Why** reason, clearer
      decision-id + next-command footer;
      `--json` on route/explain with a documented stable key contract.
- [x] **Error handling (what/why/next):** pre-init use, missing registry,
      invalid YAML, malformed model entry, invalid config.yaml, no eligible
      model, unknown decision id (suggests recent valid ids), missing SQLite
      db, `providers refresh` stub message.
- [x] **Onboarding docs:** README rewritten (status, built/not-built, fresh-clone
      quick start, storage locations, privacy note, troubleshooting, limits);
      USER_GUIDE.md created (per-command walkthrough + JSON contract).
      TESTING.md skipped deliberately — README's pytest section covers it.
- [x] **Safety review:** no auto-execution anywhere; high risk always
      human-gated (tested); task-log privacy documented + `--no-log`;
      no model names in logic (registry-only).

## 🎯 Next recommended milestone

**M3 — refresh breadth + registry hygiene:** add a second refresh adapter
(OpenAI models endpoint, read-only key), registry staleness warnings from
`last_updated`, and smarter refresh filtering (e.g. `--match`, curated ability
overrides for refreshed entries). This turns one-off refresh into a
maintainable catalog pipeline.

## 📋 Remaining pending items (next up)

1. **Second refresh adapter (openai)** reusing the M2 architecture.
2. **Registry staleness warnings:** surface `last_updated` age at load time.
3. **Refresh filtering/curation:** `--match` substring filter; way to overlay
   curated ability scores on refreshed entries without hand-editing generated files.
4. **Feedback learning loop (M4):** bounded weight adaptation from stored ratings.
5. **CI:** GitHub Actions running pytest + coverage gate.
6. **Rotate the OpenRouter key in `.env.example`** and blank the placeholder.

## Production-readiness gaps (unresolved, documented)

- `providers refresh` covers OpenRouter only; other providers remain manual YAML
- Ability scores are hand-curated (manual) or pricing heuristics (refreshed),
  not benchmarked — recommendations advisory
- Rule-based classifier only; ambiguous phrasing can misread (overrides exist)
- Feedback stored but not learned from
- No CI, no PyPI packaging/release process, no CHANGELOG
- SQLite single-user assumption; no log rotation/retention policy
- Decision log stores task text verbatim (documented; `--no-log` exists) — no
  redaction or encryption at rest

## Known limitations (by design in v1)

- Planner, not executor — never runs the recommended tool
- Single-user, local-only; no network calls at all in MVP

## Future capstone features (M2–M3)

- Live provider catalog sync via all six adapters
- Larger realistic seed registry; polished demo script

## Future production features (M6–M7)

- Real execution adapters (opt-in; high-risk always human-gated)
- Secret management; team mode (shared registry, policy, telemetry)

## Testing gaps

- No property-based/fuzz tests on classifier
- No snapshot tests of human-readable CLI output
- Coverage not measured/enforced (no CI)
- Fallback-chain edge cases lightly tested

## Security / privacy gaps

- No redaction/encryption of the local decision log
- No secret-store implementation (none needed yet — MVP uses no secrets)

## Provider integration gaps

- OpenRouter: live catalog refresh ✅ (M2). The other five adapters are
  registry entries only — no live fetch yet (spec exists)
- Refreshed metadata quality is capped by what the OpenRouter API exposes
  (no latency, no ability benchmarks)

## Documentation gaps

- No CONTRIBUTING.md / CHANGELOG.md
- Spec docs (PRD etc.) still describe Capstone+ features as future — correct,
  but sync them whenever a tier ships
