# TASK-050: Annotation boolean and integer coercion

Rust annotation schemas now match Pydantic JSON coercions for boolean fields
(booleans, numeric 0/1, and recognized string forms) and the manifest's
unsigned schema version (integer, integer-valued number, boolean, or numeric
string). The Python/Rust schema test covers the accepted forms; invalid values
remain rejected by serde or the schema validator.

Validation:

- `.venv/bin/python -m pytest -q tests/test_rust_annotation_schema_compat.py`:
  23 passed locally.
- Evaluation crate Clippy with warnings denied: passed locally.
- Hosted Linux/Windows/macOS checks are pending the next RC push.
