# TASK-043 — Python-compatible Unicode lowercase for graph IDs

Implemented Python's contextual Greek final-sigma rule when normalizing graph
node names, edge sources/targets, and prompt tokens. This makes related IDs such
as `ΟΣ` and `οσ` remain distinct exactly as Python's `str.lower()` does, while
the non-contextual lowercase mapping continues to use Rust's Unicode tables.

The focused differential checks Greek final sigma and medial sigma inside graph
dependency identifiers. Thirteen graph compatibility cases pass locally. The
graph module is now marked Parity; full suite and cross-platform confirmation
remain in progress.
