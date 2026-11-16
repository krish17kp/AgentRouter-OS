# TASK-162 evidence

The Rust registered runner now owns the same lifecycle as Python: default,
profile, and dataset selection; deterministic collection; MASSIVE language
filtering; fixture/real blockers; context generalization; classification before
model/CLI discovery; complete grading; dataset quality; and runtime provenance.

Repairs from independent audit include empty-language truthiness, preserving a
direct runner's supplied profile while normalizing CLI dataset precedence,
central invalid-source validation, combined-error precedence, hidden platform
detail, bounded five-second provenance commands, and concurrent stdout draining
for large dirty repositories. The runtime-specific environment mapping and null
semantics are specified in `RUNTIME_ENVIRONMENT_CONTRACT.md`.

Verification:

- Independent audit: clear after three repair rounds.
- Rust runner unit checks, including 3,000-file dirty output: passed.
- Full Rust workspace and strict workspace Clippy: passed.
- Runner/CLI/platform focused differential: 40 passed.
- Ruff check and format: passed.
- Full Python regression: 2,660 passed, 7 skipped in 308.85 seconds.
- TASK-161 hosted Rust migration CI: Linux/Windows/macOS success.

The runner row is promoted to Parity. Inventory is 52/77 Parity and 25 Partial.
Production readiness remains false.
