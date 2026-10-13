# Plan — TASK-003 testing-stack extras (L5)

## Goal
Exercise the declared `property` (hypothesis) and `mutation` (mutmut) extras with
real value, and begin closing the unmeasured mutation-score gap.

## Property tests (tests/test_property.py)
Strong invariants, `pytest.importorskip("hypothesis")` so absent-dep envs skip cleanly:
- classifier: confidence in [0,1]; valid enums; approval==_APPROVAL[risk];
  needs_clarification==(conf<threshold); explicit --risk always wins; deterministic.
- RateLimiter: allowed count in one window == min(n, limit) (never exceeds).
- IdempotencyCache: put->get round-trips within TTL.
- observability: record never leaks raw task text; task_len == len(task).

## Mutation testing
- Configure a scoped mutation run on a small critical module (server/limits.py).
- Environment reality (discovered): mutmut 3.x = WSL-only on Windows; mutmut 2.x =
  incompatible with Python 3.13 (pony ORM bytecode decompiler). So the DECLARED tool
  cannot run in this Windows + py3.13 env.
- Resolution: produce a real score with a py3.13/Windows-compatible runner; keep the
  declared tool available for CI/Linux. Never fabricate a score.

## Risk: low. Tests-only + config; no production code changes.
