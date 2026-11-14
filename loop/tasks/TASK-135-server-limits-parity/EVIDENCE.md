# TASK-135 evidence

## Verification

- Python/Rust server-limits compatibility suite: **8 passed**. New concurrent
  cases compare Python asyncio locks with Rust keyed computations for a shared
  successful response, non-2xx recomputation, operation failures, and parallel
  distinct keys.
- Full Rust workspace tests: passed.
- Rust formatting, targeted Ruff, Ruff formatting, and `git diff --check`: pass.
- Hosted TASK-134 MCP SDK 1.30/2.3 jobs and Rust workspace jobs on Linux,
  Windows, and macOS pass at `a900126`. Other platform suites were still
  running at this evidence checkpoint.
- The immutable context-band release gate remains unchanged at 0.6667 against
  0.90. OpenAI live smoke remains skipped without the owner credential.
