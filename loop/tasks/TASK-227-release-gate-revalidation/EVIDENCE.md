# TASK-227 Evidence

Date: 2026-11-18

## Verification

Ran the authoritative local release gate from the current checkout:

```text
.venv/bin/python -m agentrouter eval run --all --no-artifacts --require-release-ready
exit 1
Grade /100: 98.23
Cases: 165
Release-ready: NO
```

All gates pass except `context_band_accuracy>=0.90`. The JSON report records
`current_holdout.accuracy = 0.6667` and `release_ready = false`. The report also
records `git_dirty = true` because the preserved untracked historical directory
`loop/tasks/TASK-163-registry-parity-audit/` remains in the worktree.

No threshold, holdout, labels, or release data was changed.
