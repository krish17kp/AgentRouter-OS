# Coverage report — TASK-156

Run date: 2026-11-15

Platform: Linux, Python 3.12.15

## Full regression

Command: python -m pytest -q --cov=agentrouter --cov-branch

- 2,610 passed; 7 skipped; 0 failed.
- Runtime: 405.83 seconds.
- Statement coverage: 92.021% (6,943 of 7,545 statements).
- Branch coverage: 87.833% (1,978 of 2,252 branches).
- Combined coverage: 91.058%.
- The unchanged 90% statement and 85% branch thresholds pass.

The run includes default and injected Rust scorecard evaluation paths. The Rust
evaluation crate, strict Clippy, and 42 scorecard/evaluation compatibility tests
pass. Independent review found no blocking defect. This slice preserves the
Partial grading/platform status because public default grading and live CLI/model
discovery remain incomplete.
