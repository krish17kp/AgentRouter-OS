# TASK-135 evidence

## Verification

- Python/Rust server-limits compatibility suite: **8 passed**. New concurrent
  cases compare Python asyncio locks with Rust keyed computations for a shared
  successful response, non-2xx recomputation, operation failures, and parallel
  distinct keys.
- Full Rust workspace tests and strict Clippy: passed.
- Rust formatting, targeted Ruff, Ruff formatting, and `git diff --check`: pass.
- Full Python coverage regression: **2,529 passed, 5 skipped, 0 failed** in
  409.36 seconds; 91.971% statement, 87.690% branch, 90.988% combined coverage.
  Details are in `docs/COVERAGE_REPORT_2026-11-14-TASK-135.md`.
- At `934fe17`, push-workflow MCP SDK jobs, Rust workspace jobs on
  Linux/Windows/macOS, Python/Rust compatibility on all three systems, Python
  3.10–3.13, macOS and critical-module mutation pass. One Windows job and
  duplicate PR-workflow checks were still running at this evidence checkpoint.
- The immutable context-band release gate remains unchanged at 0.6667 against
  0.90. OpenAI live smoke remains skipped without the owner credential.
