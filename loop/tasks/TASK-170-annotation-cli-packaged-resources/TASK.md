# TASK-170 — Annotation CLI packaged-resource parity

Audit `agentrouter.annotation.cli` against the Rust `agentrouter-evaluate
dataset` surface in a packaged/installed runtime, not only from the repository
checkout. Candidate defaults and frozen-holdout leakage checks must remain
available without source-relative paths; explicit human labels remain the only
way to create annotations. Preserve resumable writes, blinded packs, fail-closed
adjudication, and leakage protection.

## Baseline

The Rust CLI matches the Python command set and four end-to-end differentials
already pass, but default `pack` and `build` resource reads resolve through
`CARGO_MANIFEST_DIR/../..`. That works in the source tree and can fail for an
installed binary or when invoked outside the checkout. Embed the immutable
candidate and frozen-holdout resources while retaining explicit user paths.

The source-tree file remains preferred when present so local development sees
the checked-out fixture; embedded bytes are the deterministic fallback for an
installed binary or another working directory. Embedded byte lengths, SHA-256
digests, candidate count, and holdout prompt count are asserted in Rust tests.
