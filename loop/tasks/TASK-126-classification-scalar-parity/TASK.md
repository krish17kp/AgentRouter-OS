# TASK-126 — Classification scalar parity

## Objective

Align Rust `Classification.confidence` and `Classification.needs_clarification`
with the Python/Pydantic JSON contract, and close the registry float-string
whitespace boundary exposed during the scalar compatibility audit.

## Changes

- Rust confidence accepts Pydantic-compatible numbers, numeric strings, and
  booleans, and enforces the Python 0–1 field bounds.
- Rust `needs_clarification` accepts booleans, 0/1 numeric forms, and Pydantic's
  case-insensitive boolean strings; malformed and whitespace-padded tokens are
  rejected.
- Rust float-string coercion accepts digit separators between digits but does
  not trim surrounding whitespace when separators are present, matching
  Pydantic's accepted/rejected forms.
- Added Python/Rust differential cases and Rust unit tests for accepted,
  rejected, range-boundary, and negative-zero inputs.

## Verification

- Focused schema and registry compatibility checks: 22 passed.
- Full Python suite: 2,352 passed, 4 skipped; 91.970% statements, 87.690%
  branches, 90.988% combined coverage.
- Full Rust workspace, strict Clippy, Rust formatting, Ruff check/format,
  Bandit, pip-audit, cargo audit, and diff checks pass locally.
- Hosted validation of this task: pending push.

## Remaining schema gap

`Classification.context_tokens` remains `u32` in Rust, while Python accepts
unbounded signed integers. `agentrouter/schema.py` therefore remains Partial;
this task does not claim full module parity.
