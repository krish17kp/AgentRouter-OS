# Customer review

No entry in `loop/PRODUCT_SCENARIOS.yaml` covers `doctor`/`--verify-live`
specifically yet — the closest existing scenario is "route a prompt to a
model in under 5 minutes from a clean install" (`agentrouter route "..."`),
re-run as part of this task's real-environment smoke test rather than the
CliRunner-based unit tests:

- `agentrouter init` → `agentrouter doctor` → `agentrouter doctor --verify-live`
  → `agentrouter route "polish the README" --verify-live` against a fresh
  home directory (not just mocked fixtures). PASS: truthful, fast (~1s per
  doctor invocation), no secret ever printed, output stayed readable with
  the new `environment.harness` and `usage.*` lines added.
- A first-time user who never passes `--verify-live` sees **zero** change to
  existing `doctor`/`route` output — confirmed via
  `test_verify_live_is_opt_in_and_absent_by_default` and
  `test_route_without_verify_live_has_no_usage_check_field`.
- A user who does pass `--verify-live` today sees every provider reported
  `unsupported` (accurate, not confusing-looking noise — each line names the
  provider and says plainly why: "no live usage check registered for
  '<provider>'"). This is an intentionally honest state, not a bug: no
  provider has a live-credentialed adapter in this codebase yet.

**Not scenario-tested**: an actual EXHAUSTED-quota re-rank end-to-end via the
real CLI (impossible without a registered live adapter, which is
credential-gated per `loop/BACKLOG.yaml` P2) — covered instead by
`tests/test_usage.py`'s fake-adapter tests, which exercise the identical code
path `apply_live_verification` uses.

No `PRODUCT_SCENARIOS.yaml` entry was added for `--verify-live` — it has no
real-world effect until a live adapter exists, so a scenario asserting its
current no-op behavior would test the absence of a feature rather than a
customer-facing capability. Add one when TASK P2's credentialed adapter
lands.
