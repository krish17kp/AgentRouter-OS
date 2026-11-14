# TASK-117 — Routing evaluator duplicate-key compatibility

## Objective

Match the Python routing evaluator's behavior when callers pass duplicate
model keys.

## Findings and implementation

Python builds its constraint lookup with a dictionary comprehension, so the
last supplied model for a duplicate key wins. Rust previously selected the
first match. The Rust evaluator now searches in reverse input order for that
lookup while leaving router selection and scores unchanged.

## Verification

A Python/Rust differential fixture with two entries sharing a key reproduced
the mismatch before the fix and passes after it. The complete evaluator
compatibility file passes all 30 tests, the full Rust workspace passes, and the
refreshed full Python suite passes with 2,264 tests and 4 skips at the recorded
coverage levels.
