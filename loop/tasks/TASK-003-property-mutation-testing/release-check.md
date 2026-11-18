# Release check — TASK-003 (PARTIAL)

| AC | Status | Evidence |
|----|--------|----------|
| Hypothesis property tests for core invariants | PASS | tests/test_property.py; 6 passed; verification confirmed non-vacuous (7/8 hand-mutations caught, then 8/8 after repair) |
| property tests skip cleanly w/o hypothesis | PASS | importorskip verified in fresh venv -> SKIP not error |
| mutmut configured + real mutation score | BLOCKED_ENVIRONMENT | Windows+py3.13: mutmut 2.x (pony/py3.13), 3.x (WSL-only), mutatest 3.1 (py3.13) all incompatible. Documented in KNOWN_LIMITATIONS; declared `mutation` extra kept for Linux CI. Coverage works: limits.py 95.16% via pytest --cov |
| full suite green | PASS | 405 passed |

**Verdict: PARTIAL PASS.** Property-testing objective delivered and independently verified.
Mutation-score objective honestly deferred to Linux CI/WSL (env-blocked), NOT faked.
