# TASK-133 evidence

## Verification

- Focused schema, registry CLI, and Classification compatibility tests:
  **260 passed**.
- Full Python regression on Linux/Python 3.12.15 with pytest 9.0.3:
  **2,525 passed, 5 skipped, 0 failed** in 332.46 seconds.
- Coverage: **91.970% statements** (6,895/7,497), **87.690% branches**
  (1,959/2,234), and **90.988% weighted combined** (8,854/9,731).
- Direct `agentrouter/schema.py` coverage is 100% statements and branches.
- Full Rust workspace tests and strict Clippy pass.
- Ruff check/format, Rust formatting check, and `git diff --check` pass.
- The initial full run failed when Rust build artifacts exhausted the temporary
  filesystem. Moving the build cache to `/data` and rerunning the full suite
  resolved the environment failure; the successful result above is from the
  clean rerun.

Hosted validation will run after pushing the RC commit. The frozen
context-band release gate remains unchanged at 0.6667 < 0.90.
