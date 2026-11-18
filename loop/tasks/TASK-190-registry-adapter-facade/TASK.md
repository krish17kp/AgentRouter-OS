# TASK-190 — Registry adapter facade parity

## Objective

Extend the Rust evaluation registry beyond descriptor-only discovery with the
shared adapter lifecycle contract while preserving explicit external-data
boundaries.

## Acceptance

- registered adapters expose metadata, availability, fixture/real load,
  sampling, validation, checksum, description, and prepare operations;
- fixture behavior remains offline and deterministic;
- real HuggingFace loading remains an explicit `SKIPPED_EXTERNAL` result;
- focused Rust tests, strict Clippy, formatting, and diff checks pass;
- the parity matrix remains Partial until real loader behavior is implemented.
