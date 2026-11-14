# Implementation log — TASK-003

## Files changed
- **NEW** `tests/test_property.py` — 6 Hypothesis property tests, `pytest.mark.property`,
  `pytest.importorskip("hypothesis")` so absent-dep envs skip cleanly.
- `pyproject.toml` — net UNCHANGED from original (added then reverted a [tool.mutmut] block
  and version pins after discovering the env incompatibility; only the prior [otel] extra remains).

## Property invariants covered
- classifier: confidence in [0,1]; valid enums; approval==_APPROVAL[risk];
  needs_clarification==(conf<threshold); explicit --risk wins; deterministic output.
- RateLimiter: allowed count in a window == min(n, limit).
- IdempotencyCache: put->get round-trips within TTL.
- observability: raw task text never leaks; task_len == len(task).

## Mutation testing — ENVIRONMENT BLOCKED (Windows + Python 3.13)
Attempted, all incompatible (root-caused, not looped):
- mutmut 3.6: WSL-only on Windows (upstream #397).
- mutmut 2.4.4: pony ORM bytecode decompiler IndexError on py3.13; cp1252 emoji crash.
- mutatest 3.1: needs setuptools (added), then subprocess path issue (fixed with abs path),
  then coverage-guided 0-locations (needs .coverage), then random.sample-on-set crash on py3.13.
  Its install also downgraded `coverage` and broke pytest-cov -> RESTORED (coverage 7.15.2).
Outcome: mutation score is a Linux-CI/WSL follow-up (documented in KNOWN_LIMITATIONS).
Coverage measurement DOES work: limits.py at 95.16% via `pytest --cov`.

## Deviation
Original plan assumed mutmut would run locally; it cannot on this OS+Python. Property tests
(the higher-value half) delivered; mutation execution honestly deferred, not faked.
