# AgentRouter OS — TODO / Status

> Updated after the v0.3.0 milestone pass (2026-07-08). Honest status:
> **milestones M1–M6 implemented and tested; M7 partial (by design for a
> local-first product).** 94 offline tests, 80%+ coverage gate, CI green
> locally. Nothing actionable is pending — the items below are either done,
> blocked on a one-time user action, or explicit design decisions.

## ✅ Milestone status (see MILESTONES.md for validation details)

- [x] **M1 — MVP CLI** (v0.1.0): classify → recommend + fallback → prompt +
      checklist → SQLite log; `init/route/explain/registry list/prompt generate`
- [x] **M2 — live catalog + polished demo** (v0.2.0): OpenRouter refresh,
      generated-registry storage (manual always wins), rich `explain`, `--json`
- [x] **M3 — adapter expansion & hardening** (v0.3.0): OpenAI refresh adapter
      (static family table; key required), `--match` filter, staleness warnings
      (>90 days), curated `ability_overrides.yaml` (survives re-refresh),
      mocked adapter test harness
- [x] **M4 — feedback learning loop** (v0.3.0): low ratings shift weight from
      cost to capability — bounded (step 0.01, cap +0.10, `w_cost` ≥ 0.05),
      min-sample 3, recomputed from the feedback table (reversible: delete
      feedback or `learning: false`), logged in `weight_shifts`
- [x] **M5 — read-only dashboard** (v0.3.0): `agentrouter dashboard`, stdlib
      `http.server`, GET-only, live from SQLite, HTML-escaped; zero new deps
- [x] **M6 — execution automation** (v0.3.0): `agentrouter execute <id> --yes`;
      opt-in per provider (`supports_execution` + `exec_command`, all disabled
      in seeds); high-risk / non-auto-approval decisions provably blocked
      (tested with every provider enabled); subprocess exit code propagated
- [~] **M7 — teams & telemetry** (v0.3.0, partial): `agentrouter stats
      [--json]` (decision counts, risk + pricing-tier distributions, feedback
      acceptance rate); `policy.max_pricing_tier` enforced at route time;
      team mode = shared `AGENTROUTER_HOME`. **Not built:** per-user identity,
      hosted multi-user deployment — a local-first CLI has no service surface;
      revisit only if one appears.

## ✅ Former "remaining pending items" — all addressed

1. ~~Second refresh adapter (openai)~~ → done (M3)
2. ~~Registry staleness warnings~~ → done (M3)
3. ~~Refresh filtering/curation (`--match`, ability overrides)~~ → done (M3)
4. ~~Feedback learning loop (M4)~~ → done
5. ~~PyPI publishing workflow~~ → `.github/workflows/release.yml` (build +
   trusted publishing on GitHub Release) is in place. **Blocked on a one-time
   user action:** register `agentrouter-os` on pypi.org and add the repo as a
   trusted publisher + create the `pypi` GitHub environment (steps in
   RELEASE.md). No code work remains.

## ✅ Testing gaps — closed

- [x] Seeded fuzz tests on the classifier (`tests/test_fuzz_and_fallback.py`)
- [x] Fallback-chain edge cases (declared-fallback, rule-2 tier/provider, rule-3)
- [x] Coverage measured + enforced in CI (80% gate; currently ~86%)
- [x] CLI human-readable output asserted in smoke/e2e tests

## Deliberate design decisions (not gaps)

- Ability scores are curated/heuristic/overridden — never benchmarked. A
  benchmark pipeline is a different product; `ability_overrides.yaml` is the
  supported curation path.
- Rule-based classifier; misreads are overridable (`--risk/--tool/
  --context-tokens`) and every decision is explainable.
- Decision log stores task text verbatim, locally only; `--no-log` exists and
  is documented. No encryption at rest for a local single-user file.
- No log rotation/retention policy — SQLite grows slowly (text rows); add
  retention if the file ever matters.
- Dashboard is stdlib, not FastAPI — read-only local page needs no framework.
- Generic config-driven CLI-agent refresh adapter skipped (YAGNI): each new
  adapter is one function + one dispatch-table row; build the generic layer
  when a third adapter shows real overlap.

## Blocked on user action (no code work remaining)

- **PyPI publication:** one-time trusted-publisher setup on pypi.org +
  `pypi` GitHub environment (RELEASE.md has the exact steps), then publish a
  GitHub Release.
- **Execution opt-in:** `execute` stays inert until you set
  `supports_execution: true` + `exec_command` for a provider in your own
  `providers.yaml` — intentionally never shipped enabled.

## Future ideas (explicitly out of scope for now)

- Benchmark-based ability scoring
- Per-user identity / hosted team deployment / org telemetry service
- Live refresh adapters for claude-code, cursor, cli-agent (no public catalog
  APIs today; registry entries remain the path)
- Log redaction/encryption at rest, retention policies
