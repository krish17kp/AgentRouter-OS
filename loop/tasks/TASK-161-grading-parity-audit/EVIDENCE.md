# TASK-161 evidence

The Rust default grading facade now covers every public Python `grade` mode:
classification-only and all dimensions, default and injected classifiers,
empty and populated cases, absent/explicit-null/valid/malformed context-band
evidence, and installed CLI discovery failures. Classification is computed
before model or CLI discovery, matching Python's observable callback and error
ordering. The complete deterministic all-dimension report matches Python after
removing only the two machine-dependent performance timing medians. The default
grading facade includes Python's hidden `contract` platform group without
claiming it as a public Rust CLI command.

Hosted Windows/macOS failures were traced to Cargo adding its target directory
to the probe's child PATH. Custom-environment tests now build once and execute
the grading probe directly, so missing/failing/malformed sibling CLI fixtures
are isolated on every platform.

Independent audit found and drove repairs for ordering, incomplete full-report
comparison, hidden platform detail, and the Windows executable suffix. Final
re-audit cleared promotion. Verification:

- Rust evaluation crate: 7 passed.
- Full Rust workspace: passed.
- Strict workspace Clippy: passed.
- Focused grading differential: 27 passed, 34 deselected.
- Default grading contract: 19 passed.
- Ruff check and format: passed.
- Full Python regression: 2,642 passed, 7 skipped in 343.42 seconds.

The `agentrouter/evaluation/grading.py` row is promoted to Parity. Inventory is
51/77 Parity and 26 Partial. Release readiness remains false.
