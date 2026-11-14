# Coverage Report — TASK-119 release-candidate verification

**Run date:** 2026-11-14  
**Environment:** Linux, CPython 3.12.15, pytest 9.0.3  
**Command:** `.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term --cov-report=json:/tmp/agentrouter-task119-final-coverage.json`

## Results

| Measure | Result | Gate | Status |
|---|---:|---:|---|
| Python tests | 2,268 passed, 4 skipped | all required tests pass | Pass |
| Statement coverage | 91.97% (6,895 / 7,497) | 90% | Pass |
| Branch coverage | 87.69% (1,959 / 2,234) | 85% | Pass |
| Combined coverage | 90.99% (8,854 / 9,731) | informational | Pass |

Combined coverage is covered statements plus covered branches divided by the
total statements plus branches. No thresholds were changed. The raw coverage
JSON was generated at `/tmp/agentrouter-task119-final-coverage.json`. Four
skips are credential-gated or platform-specific; live OpenAI validation still
requires the owner-provided key documented in `PRODUCTION_STATUS.md`.
