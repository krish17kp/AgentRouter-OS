# Implementation log

1. `agentrouter/harness.py` (new, 51 lines) — `HarnessInfo`, `detect_harness()`.
2. `agentrouter/usage.py` (new, ~185 lines after repair) — `UsageStatus`,
   `check_usage()`, `register_live_check()`/`unregister_live_check()`,
   `apply_live_verification()`.
3. `agentrouter/hosts.py` — added `api_hosts()` (+3 lines) and, during repair,
   `_API_HOST_PROVIDER` + `provider_for_api_host()` (+15 lines).
4. `agentrouter/diagnostics.py` — added `check_harness()`, `check_usage_for()`,
   `run_usage_checks()`; wired `check_harness` into `run_all()`.
5. `agentrouter/cli.py` — `--verify-live` on `doctor` (calls
   `diagnostics.run_usage_checks()` when set) and on `route` (calls
   `usage.apply_live_verification()` when set, inserted between control-drop
   merging and `gates_for()` so `rec`/`reason`/`exec_route` all reflect any
   re-rank); `_reason_for()` gained one branch for the quota-exhaustion shift
   string.
6. Tests: `tests/test_harness.py` (new), `tests/test_usage.py` (new),
   additions to `tests/test_diagnostics.py` and `tests/test_cli_smoke.py`.
7. `docs/architecture/img{1..4}.png` renamed via `git mv` to descriptive
   names; `docs/architecture/README.md` created; `README.md`'s Architecture
   section shortened to a link (no image embeds duplicated in two places).

**Deviations from the initial design** (all from the independent-review
repair loop, see repairs.md): `apply_live_verification` originally
concatenated both the pre-existing and freshly recomputed `excluded` lists
(duplicate entries — fixed to keep only the pre-existing list plus the new
quota-exclusion entry); `check_usage`'s `timeout` argument was accepted but
never enforced (fixed with a bounded `ThreadPoolExecutor` + `wait()`, chosen
over `future.result(timeout=...)` because `concurrent.futures.TimeoutError`
became an alias of the builtin `TimeoutError` in Python 3.11, which would
have misclassified an adapter's own raised `TimeoutError` as our wall-clock
timeout — caught by re-running the test suite on this machine's Python 3.12);
adapter-supplied `detail` text was not sanitized (fixed, mirroring
`hosts._sanitize`); `diagnostics.check_usage_for` looked up `_LIVE_CHECKS` by
API host id while `cli.py`/`usage.py` looked up by `ModelEntry.provider` id —
two different registries for what a user would assume is "the same provider"
check (fixed via `hosts.provider_for_api_host()`); a non-OK `Check` from
`check_usage_for` had no `remedy`, contradicting `Check`'s own documented
contract (fixed).
