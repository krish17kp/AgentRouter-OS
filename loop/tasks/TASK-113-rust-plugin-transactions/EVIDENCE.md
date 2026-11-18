# TASK-113 evidence — Rust plugin replacement and transaction recovery

## Delivered locally

- Rust forced installation now creates a private replacement stage and records
  its file identity before moving the existing destination. The existing file
  remains at its original path until that identity is durable.
- The transaction journal now distinguishes `backing_up` intent from committed
  `backed_up` state. Recovery removes or restores an object only when its
  recorded path, identity, digest, mode, ownership, and journal phase agree.
- Python and Rust accept the same journal shape and recovery phases. Journal
  validation binds destinations to the selected plugin manifest and requires
  the canonical `<destination>.agentrouter-bak` backup path. Invalid but valid-
  JSON journals cannot redirect deletion at an unrelated file.
- Ambiguous concurrent edits, byte-identical files with different identities,
  unexpected backup collisions, unrecorded stages, and mismatched stage files
  are preserved for manual inspection. Recovery does not infer ownership from
  matching bytes or a colliding same-inode backup.
- The Windows rename helper now opens and verifies the destination parent by
  handle before the relative no-replace rename. This local repair targets the
  Windows failures observed in hosted CI at `08c019e`; it is not yet hosted-
  verified.

## Regression coverage

The Python and Rust tests cover backup-intent collisions, same-inode collisions,
byte-identical concurrent destinations, staged replacement identity commit,
crashes before and after moving the original, rollback cleanup interruption,
state persistence interruption, completed replacement recovery, malformed
journals, forged destination/backup paths, and preservation of unrelated files.
The focused plugin suite reports **116 passed**.

The independent TASK-112 reviewer's final audit found no remaining actionable
issue in the transaction-validation and recovery paths after the destination
allowlist and canonical-backup checks were added.

## Verification

Run on Linux, Python 3.12.15:

- Full Python regression with coverage: **2,257 passed, 4 skipped**.
- Statement coverage: **91.97%** (6,895 / 7,497); branch coverage: **87.69%**
  (1,959 / 2,234); combined statement and branch coverage: **90.99%**.
- Rust workspace: **161 tests passed**.
- Strict workspace Clippy, Rust formatting, focused Ruff check/format,
  configured Bandit, `pip-audit`, `cargo audit`, and `git diff --check`: pass.
- The hosted run at `08c019e` failed Windows Rust rename/staging cases and nine
  Windows Python/Rust plugin compatibility cases. Linux/macOS Rust and
  Python/Rust compatibility jobs passed. The changed Windows helper must pass
  the next hosted run before this lifecycle slice is marked cross-platform
  complete.

Raw coverage JSON for this run was `/tmp/agentrouter-task113-coverage.json`;
the durable summary is in `docs/COVERAGE_REPORT_2026-11-14-TASK-113.md`.

## Remaining limits

Managed plugin upgrades are not part of this contract. The broader Rust public
module inventory remains incomplete, Python remains the shipping authority,
and TASK-113 hosted Windows verification is pending. The frozen context-band
release gate remains unchanged at 0.6667 against 0.90.
