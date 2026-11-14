# TASK-052: Annotation manifest integer coercion

Manifest schema versions and count maps now accept Pydantic-compatible integer
inputs: signed integers, numeric strings, booleans, and integral floats. Count
maps now preserve signed values as Python does. Added differential cases for
those forms. Annotation schema parity remains Partial because datetime and
other edge coercions still need work.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_annotation_schema_compat.py`:
  23 passed locally.
- Evaluation crate Clippy with warnings denied: passed locally.
- Cross-platform CI follows the RC push.
