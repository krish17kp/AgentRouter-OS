# TASK-125 evidence

## Failure reproduced

The pushed commit `593e375` passed the registry-only fixture suite but failed
the evaluator compatibility path on Linux. `agentrouter-evaluation` enables
`serde_json/arbitrary_precision`; JSON numbers then reach the derived untagged
`PydanticScalar` through serde_json's private one-entry map representation.
The prior enum rejected it. CI reported failures in injected classifier,
legacy-gold routing, duplicate-model-key, and measured performance evaluator
compatibility cases. The same compatibility suites failed on Windows and macOS.

## Repair

`PydanticScalarVisitor` accepts ordinary scalar visitor calls and decodes only
the exact serde_json private number-map representation. YAML loading rejects
that reserved marker recursively before registry schema conversion. This keeps
JSON stream compatibility while refusing the internal marker in YAML input.

## Verification results

- `./.venv/bin/pytest -q tests/test_cli_registry_rust_compat.py tests/test_evaluation_metrics_rust_compat.py` — 108 passed.
- `cargo test -p agentrouter-registry --locked` — 22 passed.
- `cargo test --workspace --locked` — passed, including doctests.
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` — passed.
- `cargo fmt --all -- --check` — passed.
- `./.venv/bin/pytest --cov=agentrouter --cov-branch --cov-report=term` — 2,332 passed, 4 skipped, 0 failed; 91.983% statement, 87.735% branch, 91.008% combined.
- `./.venv/bin/ruff check .` and `./.venv/bin/ruff format --check .` — passed.
- `git diff --check` — passed.

The implementer performed a self-review of the visitor, reserved-marker guard,
and differential tests. An independent human review has not been obtained.
Hosted revalidation is pending the authorized release-candidate push.
