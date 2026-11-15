# Coverage report — TASK-155

Run date: 2026-11-15

Platform: Linux, Python 3.12.15

## Full regression

Command: `python -m pytest -q --cov=agentrouter --cov-branch`

- 2,609 passed; 7 skipped; 0 failed.
- Runtime: 437.64 seconds.
- Statement coverage: 92.021% (6,943 of 7,545 statements).
- Branch coverage: 87.833% (1,978 of 2,252 branches).
- Combined coverage: 91.058%.
- The unchanged 90% statement and 85% branch thresholds pass.

The run includes fail-closed supplied holdout validation and all existing
Python/Rust compatibility checks. The full Rust workspace, all 40 evaluation
compatibility tests, strict Clippy, Ruff, and formatting pass. Independent
review found and verified the explicit JSON-null parity repair. No release
threshold or frozen evaluation input changed.
