# TASK-160 evidence

The Rust facade export order and complete packaged `ModelEntry` JSON already
match Python. All seven re-exported evaluator modules now have individual
differential parity. Rust now caches the one validated embedded catalog with
`OnceLock`, matching Python's single-entry `lru_cache`, while returning safe
owned clones to callers. No-argument provider/performance/platform wrappers and
clearly named explicit/injected facade aliases preserve both Python call forms
despite Rust not supporting default arguments.

Independent audit rejected permanent error caching and missing default wrappers,
then rejected hiding explicit/injected variants. Both rounds were repaired and
final re-audit is clear. Rust evaluation tests (7), strict Clippy, 19 focused
facade/dimension checks, and full Python regression (2,630 passed, 7 skipped in
221.29 seconds) pass. The facade row is promoted to Parity; inventory is now
50/77 Parity and 27 Partial.
