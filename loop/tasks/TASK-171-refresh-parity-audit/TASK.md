# TASK-171 — Provider refresh parity audit

Audit `agentrouter.refresh` against the Rust provider refresh path: fixed HTTPS
catalog fetches, key-only headers, bounded responses, redirect refusal,
OpenRouter/OpenAI mapping and warnings, previous-catalog deprecation reporting,
atomic generated-file replacement, provenance, dry-run behavior, and manual
registry preservation. Keep network and credentials optional in tests.

## Baseline

Rust already implements the live provider adapters in
`agentrouter-cli::providers`, with Python-compatible conversion in
`agentrouter-registry::refresh`. Existing Rust unit tests cover bounded HTTP,
auth-header-only transport, redirect refusal, response caps, and atomic writes;
offline Python/Rust differentials cover mapping and payload filtering. The
matrix row remains Partial pending a complete audit of the public refresh
surface and CLI safety behavior.

## Implementation and evidence

- Fixed generated-catalog writes to open the configured registry with the same
  no-follow/reparse-point traversal used by home initialization; a linked
  registry directory cannot redirect writes outside the configured home.
- Added a Unix escape regression, bounded transport coverage, auth-header-only
  assertions, redirect refusal, response caps, atomic replacement, provenance,
  and manual-registry preservation tests.
- Added a feature-gated `test-fixtures` transport seam that accepts only a local
  fixture path. The production path still uses fixed HTTPS provider endpoints;
  the seam enforces the same OpenAI key precondition.
- Added a process-level Python/Rust differential covering OpenRouter success,
  warnings/deprecation reporting, dry-run no-write behavior, generated-file
  provenance and model artifacts, malformed-fetch no-write behavior, OpenAI
  success with a fixture key, and OpenAI missing-key failure.
- Verification: focused process/preflight checks 2 passed; Rust provider tests
  5 passed; full Rust workspace and strict Clippy passed (including the fixture
  feature); full Python regression 2,732 passed, 7 skipped.

The provider refresh row is ready for parity promotion after independent
review. The fixture seam is test-only and is not exposed as a production URL or
endpoint override.
