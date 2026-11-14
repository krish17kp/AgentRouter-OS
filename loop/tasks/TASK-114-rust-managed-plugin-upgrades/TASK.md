# TASK-114 — Rust managed plugin upgrades

## Objective

Complete Rust parity for upgrading a plugin file that the ownership record
proves AgentRouter installed. Match Python's automatic upgrade behavior without
requiring `--force`, while preserving the original unmanaged backup and
refusing any edit or identity change.

## Contract cases

- An unchanged managed file at the current bundled digest remains a no-op.
- An unchanged managed file with an older recorded digest is replaced with the
  currently bundled bytes and reports `updated (managed payload)`.
- The ownership record keeps its disposition and any original backup path,
  digest, identity, and mode while updating only installed digest and identity.
- An edited, linked, hard-linked, missing, or concurrently changed managed file
  is never overwritten or claimed; no backup is changed.
- A destination collision during no-clobber creation restores the prior managed
  payload when it can be proven and preserves concurrent data otherwise.
- Python-created ownership state remains readable by Rust and Rust-updated
  state remains readable by Python.

## Verification

Add a Python/Rust differential test that starts from a recorded older managed
payload, including a prior unmanaged backup. Run focused plugin tests, Rust
workspace and strict Clippy, the full Python regression and coverage, configured
security audits, and hosted Linux/Windows/macOS Python/Rust compatibility.
Keep TASK-113's cross-platform Windows rename repair under active CI validation.

## Implementation and current evidence

Rust now upgrades only a file whose recorded digest and identity still match.
It journals the intended temporary path before creating the new payload, then
records the payload identity before staging the old file. Recovery handles the
prepared, staged, published, state-committed, and linked-restore crash points;
an unverified temporary file or any concurrent state change is preserved. The
existing backup path, digest, identity, mode, and disposition survive the
upgrade. Python/Rust compatibility now covers the lifecycle and backup record.

- The seven focused Rust managed-upgrade recovery tests pass.
- The complete locked Rust workspace passes; strict Clippy, `cargo fmt`, Ruff,
  and `git diff --check` pass.
- Full Python regression and coverage pass on pytest 9.0.3: 2,262 passed,
  4 skipped; 91.96% statement, 87.65% branch, and 90.97% combined coverage.
- The independent recovery review found no remaining blocker.
- Hosted Linux, Windows, and macOS checks are pending the authorized RC push.
- The complete critical-module mutation campaign passes: 1,686 mutants,
  0.9698 overall, 0.9670 safety/policy/execution, 0.9815 routing, and zero
  unreviewed survivors. The 51 equivalent survivors are explicitly reviewed
  in `mutation-survivor-allowlist.json`; full numbers are in
  `docs/MUTATION_REPORT_2026-11-14-TASK-114.md`.
- `pip-audit` initially identified pytest 8.4.2 (CVE-2025-71176). The dev
  constraint now requires patched pytest 9.0.x, and `pip-audit` passes.
