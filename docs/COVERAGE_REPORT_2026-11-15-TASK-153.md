# Coverage report — TASK-153

Run date: 2026-11-15

Platform: Linux, Python 3.12.15

## Full regression

Command: `python -m pytest -q --cov=agentrouter --cov-branch`

- 2,597 passed; 7 skipped; 0 failed.
- Runtime: 501.42 seconds.
- Statement coverage: 92.004% (6,938 of 7,541 statements).
- Branch coverage: 87.789% (1,977 of 2,252 branches).
- Combined coverage: 91.034%.
- The unchanged 90% statement and 85% branch thresholds pass.

The run covers strict diagnostic-bundle redaction, JSON-safe masking, UTF-8
artifact bounds, sensitive field handling, and the Python/Rust differential.
The full Rust workspace, strict Clippy, Ruff, formatting, wheel and sdist build,
and installed-wheel CLI/API/MCP/plugin smoke also pass. Independent Python and
Rust review found no blocking issue. The frozen routing evaluation remains
unchanged and below its separate release threshold.
