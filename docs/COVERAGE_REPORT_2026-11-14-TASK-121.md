# Python coverage report — TASK-121

Date: 2026-11-14  
Environment: Linux, CPython 3.12.15, pytest 9.0.3  
Command: `pytest --cov=agentrouter --cov-branch --cov-report=term`

## Results

- 2,274 passed, 4 skipped; one upstream Starlette/httpx deprecation warning.
- Statements: 6,895 / 7,497 covered (91.97%).
- Branches: 1,959 / 2,234 covered (87.69%).
- Combined coverage: 90.99%.
- Project gates: at least 90% statement and 85% branch coverage; both pass.

The suite includes the Rust/Python CLI onboarding and evaluator alias
differentials. Coverage is measured over the Python `agentrouter` package, so
Rust implementation paths are validated by their workspace and differential
tests rather than included in these Python coverage percentages.
