# TASK-049: Annotation confidence scalar coercion

Pydantic accepts numeric strings and booleans for `confidence` values and
normalizes them to JSON floats. Rust's annotation schema now accepts the same
forms for both annotator labels and adjudicated items. Added Python/Rust
differentials for numeric-string and boolean confidence inputs. The broader
annotation schema remains Partial until datetime parsing and remaining scalar
coercions are complete.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_annotation_schema_compat.py`:
  18 passed locally.
- Evaluation crate Clippy with warnings denied: passed locally.
- Cross-platform hosted checks start after the RC push.
