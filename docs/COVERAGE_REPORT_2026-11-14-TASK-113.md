# Coverage Report — TASK-113

**Run date:** 2026-11-14

**Environment:** Linux, CPython 3.12.15

**Command:** `.venv/bin/python -m pytest -q --cov=agentrouter --cov-branch --cov-report=json:/tmp/agentrouter-task113-coverage.json --cov-report=term`

## Results

| Measure | Result | Gate | Status |
|---|---:|---:|---|
| Python tests | 2,257 passed, 4 skipped | all required tests pass | Pass |
| Statement coverage | 91.97% (6,895 / 7,497) | 90% | Pass |
| Branch coverage | 87.69% (1,959 / 2,234) | 85% | Pass |
| Combined coverage | 90.99% (8,854 / 9,731) | informational | Pass |

Combined coverage is covered statements plus covered branches divided by the
total statements plus branches. No thresholds were changed. The raw coverage
JSON was generated at `/tmp/agentrouter-task113-coverage.json` during
verification; this report preserves the measured totals in the repository.
