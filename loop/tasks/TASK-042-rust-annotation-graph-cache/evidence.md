# TASK-042 — Python-compatible graph signal cache

Added the `functools.lru_cache(maxsize=4)` behavior to the Rust graph loader.
Cache keys preserve the supplied path spelling; hits update recency; missing,
unreadable, and invalid-JSON fallbacks are cached; malformed graph-shape errors
are not cached; and the least-recently-used entry is evicted at capacity.

A same-process Python/Rust sequence differential exercises stale hits, five
distinct paths, max-size eviction, and a cached missing-file fallback. The
graph module stays Partial because exact Python contextual Unicode lowercase
behavior for graph edge identifiers still needs a differential and port.
