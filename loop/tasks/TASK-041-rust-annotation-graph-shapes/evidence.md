# TASK-041 — Rust annotation graph shape behavior

The graph signal now matches Python's behavior for JSON root types, iterable
`nodes`/`edges` values, falsey fallback from `edges` to `links`, ignored
non-mapping entries, and erroring on non-iterable truthy scalar collections.
This preserves the optional graph feature's intended fallback for missing,
unreadable, and invalid-JSON files while matching Python's errors for valid JSON
with malformed shapes.

Eleven graph differential cases pass locally, including seven new malformed or
mapping-iteration cases. The Python LRU cache behavior (`maxsize=4`) remains
unported, so the parity inventory continues to mark this module Partial.
