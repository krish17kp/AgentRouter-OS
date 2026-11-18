# TASK-193 — Final local release verification

## Objective

Re-run the optimized Rust build and dependency audit after the final local
parity/test slices, then record the exact release-candidate evidence.

## Acceptance

- locked optimized workspace build passes;
- release binary version/help smoke passes;
- dependency audit reports no vulnerability advisories;
- any unmaintained dependency warning is recorded honestly;
- no tag, publication, deployment, or hosted gate bypass occurs.
