# Coverage Report — TASK-114/115/116 local candidate

**Run date:** 2026-11-14
**Environment:** Linux, CPython 3.12.15, pytest 9.0.3
**Command:** `.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:/tmp/agentrouter-task116-coverage.json`

## Results

| Measure | Result | Gate | Status |
|---|---:|---:|---|
| Python tests | 2,263 passed, 4 skipped | all required tests pass | Pass |
| Statement coverage | 91.96% (6,894 / 7,497) | 90% | Pass |
| Branch coverage | 87.65% (1,958 / 2,234) | 85% | Pass |
| Combined coverage | 90.97% (8,852 / 9,731) | informational | Pass |

Combined coverage is covered statements plus covered branches divided by the
total statements plus branches. No thresholds were changed. Raw coverage JSON
was generated at `/tmp/agentrouter-task116-coverage.json`; this report preserves
the measured totals in the repository. This run used the patched pytest version
required by the development dependency constraint.
