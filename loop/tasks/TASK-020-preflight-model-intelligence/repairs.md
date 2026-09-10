# Repair loop

## 0. CI-only findings (not caught by local runs before the first push)

**0a. Harness test asserted the wrong thing for the ambient environment.**
`tests/test_harness.py::test_detect_harness_defaults_to_the_real_process_environment`
asserted `detect_harness()` (no args, real `os.environ`) equals `claude-code`
— true only in the implementer's interactive session (`CLAUDECODE` set),
false in GitHub Actions CI (`GITHUB_ACTIONS=true` is the honest, correctly
detected answer). `detect_harness()` itself was correct in both places; the
test's expectation was environment-dependent. Fixed by controlling
`os.environ` via `monkeypatch.setenv` instead of trusting the ambient
environment. Caught by: every CI job (3.10-3.13, Windows) failing identically
on this one assertion; local runs never disagreed because they always ran
inside the same Claude Code session.

**0b. Mutation gate `no_tests` on the two new hosts.py functions.**
PR #15's `critical-modules` job failed `selected_results_complete` — group
and overall *scores* were identical to the historical passing baseline
(0.986/0.9879/0.9815, 0 unreviewed survivors), which initially looked like
flakiness, but reproduced identically across two independent CI runs.
Downloaded the run's `critical-mutation-report` artifact and grepped
`mutmut.log` directly: the two `no_tests` (🫥) mutants were exactly
`agentrouter.hosts.x_api_hosts__mutmut_1` and
`agentrouter.hosts.x_provider_for_api_host__mutmut_1` — deterministic, not
random. Root cause: `pyproject.toml`'s `[tool.mutmut]
pytest_add_cli_args_test_selection` is a fixed, hand-curated list of test
files run against `hosts.py` mutants — not coverage-based auto-discovery.
The only test for these two new functions lived in `tests/test_diagnostics.py`,
which isn't in that list, so mutmut never attempted a single test against
their mutants. Fixed by adding direct tests to `tests/test_mutation_kills.py`
(which is in the curated list, and is this project's existing convention for
closing exactly this class of gap). Verified locally before re-pushing:
`mutmut run` scoped to just these two functions showed both 🎉 (killed), was
both 🫥 (no_tests).


## 1. Duplicated `excluded` entries (product-architect, correctness)
**Reproduce**: constructed a route with one model whose context window always
fails eligibility; after a live-EXHAUSTED re-rank, that model's exclusion
reason appeared twice in `result["excluded"]`.
**Classify**: implementation bug — `retry["excluded"]` (recomputed via
`eligibility()` on `models - {top}`) is a pure-function duplicate of the
eligibility portion already in `result["excluded"]`, since eligibility never
depends on which other models are present.
**Root cause fix**: `agentrouter/usage.py` — drop the `*retry["excluded"]`
spread; keep `[*result["excluded"], drop_entry]` only.
**Regression test**: `tests/test_usage.py::test_apply_live_verification_does_not_duplicate_eligibility_exclusions`.
**Re-verify**: `pytest tests/test_usage.py -q` green; full suite green.

## 2. Unenforced timeout (security, MEDIUM-1)
**Reproduce**: registered a fake adapter sleeping 1.5s with `timeout=0.05`;
`check_usage` returned only after ~1.5s (the "bounded timeout" the CLI help
promises was not real).
**Classify**: implementation bug — contract violation (the code claimed a
guarantee it didn't enforce).
**Root cause fix**: `agentrouter/usage.py` — run the adapter in a
`ThreadPoolExecutor`, use `concurrent.futures.wait([future], timeout=timeout)`
to detect non-completion, `shutdown(wait=False)` to avoid blocking on an
abandoned thread. Deliberately does NOT use `future.result(timeout=...)`,
because on Python ≥3.11 `concurrent.futures.TimeoutError` is the same class
as the builtin `TimeoutError`, which would misreport an adapter's own raised
`TimeoutError` as our wall-clock timeout — caught by the fix's own first
test run on this machine (Python 3.12), which failed
`test_a_registered_check_that_raises_is_isolated_as_error_not_propagated`
with exactly that misattribution.
**Regression tests**: `test_a_slow_check_is_bounded_by_timeout_not_left_to_hang`,
`test_a_fast_raise_is_reported_as_the_adapters_error_not_a_timeout`.
**Re-verify**: targeted + full suite green.

## 3. Unsanitized adapter `detail` (security, MEDIUM-2)
**Reproduce**: a hostile `detail` string with ANSI escape codes and an
oversized length reached `status.detail` verbatim (would reach stdout, the
route JSON payload, and the SQLite decision log via `store.save_decision` /
`explain`).
**Classify**: real gap in an existing established pattern
(`hosts._sanitize()` exists precisely to close this class of risk for CLI
host output; the new module didn't apply the equivalent).
**Root cause fix**: `agentrouter/usage.py` — added `_sanitize()` (same
approach as `hosts._sanitize`), applied to a live check's returned `detail`
before it leaves `check_usage`.
**Regression test**: `test_a_registered_check_cannot_inject_control_characters_or_ansi_escapes`.
**Re-verify**: targeted + full suite green; bandit still 0 issues.

## 4. Inconsistent `_LIVE_CHECKS` key namespace (security, MEDIUM-3)
**Reproduce**: registered a fake adapter under the provider id `"openai"`;
`doctor --verify-live` (which looked up by host id `"openai-api"`) reported
UNSUPPORTED while `route --verify-live` (looked up by `"openai"`) would have
fired the adapter — same account, two different answers depending on which
command the user ran.
**Classify**: design inconsistency — a real defect the two call sites
disagreed on the same underlying fact.
**Root cause fix**: `agentrouter/hosts.py` — added
`_API_HOST_PROVIDER`/`provider_for_api_host()`, the single source of truth
mapping an API host id to its provider id (from `registry/seeds/providers.yaml`:
anthropic-api→anthropic, openai-api→openai, gemini-api→google,
openrouter→openrouter). `diagnostics.check_usage_for` now converts through it
before calling `usage.check_usage`.
**Regression test**: `test_verify_live_and_route_verify_live_query_the_same_provider_key`.
**Re-verify**: targeted + full suite green.

## 5. Non-OK Check without a remedy (security, LOW-1)
**Reproduce**: `check_usage_for`'s EXHAUSTED/ERROR branches returned
`Check(..., remedy=None)`, contradicting `Check`'s own documented contract
("required whenever the status is not ok" — `diagnostics.py`'s docstring).
**Classify**: contract violation, low severity (unreachable via a FAIL-severity
path today, since the severity map never yields FAIL for a usage check).
**Root cause fix**: `agentrouter/diagnostics.py` — added a remedy string per
non-OK usage state.
**Regression test**: `test_exhausted_usage_check_is_a_warning_with_a_remedy`.

## 6. Minor style (product-architect)
`agentrouter/harness.py` — moved `from os import environ` (function-local) to
a module-level `import os`. No behavior change; no dedicated test needed
(covered by the existing harness tests still passing).

## Accepted, not changed
- LOW-2 (unguarded `register_live_check` global): accepted per
  security-reviewer-arros's own recommendation — not attacker-reachable
  today; revisit when an in-process extension mechanism exists.
- `_LIVE_CHECKS` registry vs. direct dispatch (product-architect judgment
  call): accepted — task.yaml's acceptance criteria explicitly require a
  pluggable, test-provable mechanism.
- Single-level re-rank ceiling: accepted, documented with a `ponytail:`
  comment in `usage.py` rather than built out further (unreachable while
  `_LIVE_CHECKS` is empty in production).
