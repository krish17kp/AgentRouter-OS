# TASK-119 — Rust legacy gold error and JSON parity

## Objective

Close the remaining observable error and artifact-encoding differences between
the Rust legacy gold evaluator and `agentrouter/evaluate.py`.

## Implementation

- Add typed Rust load failures with Python-compatible `GoldError`, YAML, and OS
  categories while retaining the matching semantic error messages.
- Preserve the Python CLI's `Benchmark error` diagnostic for gold load errors.
- Escape non-ASCII JSON string characters as lowercase `\\u` sequences,
  including UTF-16 surrogate pairs for non-BMP characters, so artifact bytes
  match Python's `json.dumps(..., ensure_ascii=True)` behavior.
- Add Python/Rust comparisons for invalid gold files, CLI errors, and Unicode
  artifact bytes; update the public-module parity inventory.

## Verification

Focused legacy gold tests pass, as do the full Rust workspace, strict Clippy,
Rust formatting, Ruff checks/formatting, and diff checks. Hosted Python jobs
found and stopped on two Ruff formatting mismatches; the local formatter repair
is ready to push. Full Python regression and hosted cross-platform verification
are in progress.
