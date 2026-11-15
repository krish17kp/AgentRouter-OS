# TASK-158 evidence

Rust evaluation CLI now rejects unknown options for read-only commands, rejects
all options on Python's option-free `status` command, rejects trailing `report`
arguments, and returns usage exit code 2 for missing report/compare paths and a
missing prepare selection. Report, comparison artifacts, preparation blockers,
status output, context-band JSON, missing files, and argument errors have direct
CLI coverage.

TASK-157's hosted cross-platform failure was also repaired: Ruff formatting is
clean across all 592 Python files. Independent review found two argument-shape
gaps; both were repaired and re-reviewed clear. Verification: 43 focused
Python/Rust CLI tests, Rust evaluation tests and strict Clippy, full Rust
workspace/strict Clippy, Ruff check/format, and full Python regression with
2,626 passed and 7 skipped in 350.34 seconds.

The evaluation CLI row remains Partial for external real-dataset preparation
and remaining complete public Typer behavior.
