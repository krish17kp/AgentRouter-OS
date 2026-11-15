# TASK-159 evidence

`platform.py` has one public evaluator plus two runtime discovery helpers.
Exact Python/Rust differential tests cover the live Python manifest, empty,
partial, duplicate, private, and complete injected manifests, including sorted
details, missing entries, present/expected counts, and four-decimal score.

TASK-143/TASK-157 runtime coverage queries the installed Rust `agentrouter`
surface and compares the report to that executable. TASK-159 adds real process
fixtures for absent, nonzero, malformed, and unknown-field CLI responses and
checks the reported surface against the CLI's declared top-level help contract.
TASK-158 validates the surrounding CLI option and error contracts. The manifest
is an explicit bounded Rust CLI contract rather than runtime command reflection.

Independent audit initially rejected the promotion for missing process-level
and dispatch-consistency evidence. After those gaps were repaired, re-audit was
clear. Verification passes: 12 focused platform/default-runtime differentials,
Rust evaluation tests and strict Clippy, and full Python regression with 2,630
passed and 7 skipped in 308.40 seconds. The 77-row matrix count is mechanically
confirmed at 49 Parity and 28 Partial.
