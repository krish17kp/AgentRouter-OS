# TASK-233 Evidence

Date: 2026-11-18

## Verification

Added `agentrouter/reliability/__main__.py`, delegating to the existing soak
parser and lifecycle. The package-level help subprocess exits 0 and exposes
`--seconds`, `--workers`, `--batch`, `--home`, and `--out`.

```text
tests/test_soak.py                         7 passed
tests/test_rust_reliability_compat.py     12 passed
```

The complete regression suite was then rerun against the new entrypoint:

```text
2743 passed, 7 skipped, 1 warning in 196.82s
```

The remaining reliability Partial status is unchanged: native transport phase
taxonomy, platform resource sampling, and broader lifecycle parity still need
separate evidence.
