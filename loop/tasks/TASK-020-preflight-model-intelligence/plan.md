# Plan

**Strategy**: extend existing abstractions, invent nothing that already exists.
No new top-level CLI command (`doctor`/`route` already fit); no new catalog,
state-enum, or scoring algorithm; two small new modules only where a real gap
existed (harness identity, usage/quota state).

**Files changed**:
- `agentrouter/harness.py` (new) — introspective harness detection.
- `agentrouter/usage.py` (new) — usage/quota state + `apply_live_verification`
  (re-rank glue that reuses `engine.route()` unchanged, mirroring how
  `hosts.execution_route_block` and `controls.apply_controls` already sit
  beside — not inside — the pure engine).
- `agentrouter/diagnostics.py` — `check_harness()` (always-on), `check_usage_for()`
  / `run_usage_checks()` (opt-in, `_safe()`-isolated per provider).
- `agentrouter/hosts.py` — `api_hosts()` accessor, `provider_for_api_host()`
  mapping (added during repair — see repairs.md MEDIUM-3).
- `agentrouter/cli.py` — `--verify-live` on `doctor` and `route`;
  `_reason_for()` explains a quota-triggered re-rank.
- `docs/architecture/*.png` renamed to descriptive names; `docs/architecture/README.md`
  landing page added; root `README.md` architecture section shortened to link
  there (separate concern, same branch, see the commit split below).

**Migration**: none — every new field/flag is additive and opt-in.

**Test strategy**: unit tests for `harness.py`/`usage.py` in isolation
(no network), CLI-level tests via `CliRunner` proving the opt-in flags are
true no-ops by default, and one CLI-level end-to-end assertion that
`route --verify-live`'s JSON payload carries `usage_check` while a plain
`route` never does.

**Rollback**: revert the commit(s) on this branch; nothing is migrated,
nothing else depends on the new modules yet.

**Docs**: `AGENT_HANDOFF.md`/`LOOP_STATE.json`/`LOOP_LOG.md` updated at RECORD
time (see handoff.md). No user-facing docs beyond `--help` text needed a
rewrite — `doctor --help` / `route --help` carry the new flag's explanation
inline, matching this repo's existing convention of Typer help strings as the
primary CLI documentation.

**Release impact**: none of the seven evaluation gates, mutation gate, or
contract version are touched. This does not move the RC's release-readiness
verdict (`context_band_accuracy` gate is unrelated and unchanged).
