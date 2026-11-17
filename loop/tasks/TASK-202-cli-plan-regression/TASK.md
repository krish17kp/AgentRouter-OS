# TASK-202 — CLI plan regression coverage

## Objective

Keep the unified CLI planning contract protected by a Python/Rust process-level
test, including explicit policy flags that must remain non-executing.

## Acceptance

- initialize and save a real Rust route in an isolated home;
- compare the JSON plan's status and command preview;
- assert `execution_enabled` remains false with `--allow-remote --approve`;
- run through the repository's unified CLI fixture and locked workspace build.
