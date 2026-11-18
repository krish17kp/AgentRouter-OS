# TASK-217 Evidence

Date: 2026-11-18

Rust bundle `decision_shape` now uses `symlink_metadata` for `size_bytes` after
the SQLite no-follow open, closing the remaining path-following read in that
collector. Existing bundle tests and the full workspace checks remain the
verification authority; complete handle-native SQLite parity is still open.
