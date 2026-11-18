# TASK-235 Evidence

Date: 2026-11-18

## Verification

Ran:

```text
python -m agentrouter eval run --all --no-artifacts --require-release-ready
```

Result: exit 1, score 98.23/100, 165 cases, `release_ready: false`. Six gates
pass; the sole failure remains `context_band_accuracy>=0.90` at `0.6667`. No
holdout, threshold, or evaluation input was modified.
