# Coverage report — TASK-154

Run date: 2026-11-15

Platform: Linux, Python 3.12.15

## Full regression

Command: `python -m pytest -q --cov=agentrouter --cov-branch`

- 2,604 passed; 7 skipped; 0 failed.
- Runtime: 561.79 seconds.
- Statement coverage: 92.021% (6,943 of 7,545 statements).
- Branch coverage: 87.833% (1,978 of 2,252 branches).
- Combined coverage: 91.058%.
- The unchanged 90% statement and 85% branch thresholds pass.

The run covers exclusive creation of Python diagnostic artifacts and all existing
Python/Rust compatibility checks. Focused bundle/observability tests pass 95/1,
hooks pass 33/33, Bandit is clean, wheel/sdist build passes, and an installed-wheel
smoke confirms an existing artifact is preserved. Independent review found no
blocking issue.
