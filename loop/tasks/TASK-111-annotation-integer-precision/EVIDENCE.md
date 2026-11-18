# TASK-111 evidence

## Reproduced mismatch

Python Pydantic accepted an 80-digit manifest integer, while the Rust probe
rejected it with `value must be an integer` because it stored schema versions
and count values as `i64`.

## Local implementation and verification

- Rust now preserves manifest integers as `serde_json::Number` with the
  `arbitrary_precision` feature and matches Python normalization for booleans,
  integral floats in the supported coercion range, signed/underscored/zero-
  padded integer strings, and integral decimal strings.
- Differential cases check exact round-trip of 80-digit positive/negative
  values in `schema_version` and each count map, plus leading-zero and
  integral-decimal strings and Python's supported float-to-int boundary.
- Manifest storage now round-trips the same large integers byte-for-byte with
  the Python serializer and loads them from either runtime.
- The serializer feature changes how JSON numbers cross into YAML serializers.
  Annotation dataset/candidate writes and generated provider-catalog writes
  convert supported values to native YAML primitives and reject an unsupported
  oversized integer instead of silently converting it to an inexact float.
  Provider refresh has a Rust regression test for numeric fields.
- Focused annotation schema/store/compare/packs/CLI Python-Rust compatibility:
  71 passed.
- Full Python regression: 2,229 passed, 4 skipped; 6,717 / 7,234 statements,
  1,896 / 2,138 branches, 91.90% combined coverage.
- Full Rust workspace tests, strict Clippy, Rust formatting, Ruff check/format,
  and `git diff --check` pass locally.
- Hosted cross-platform CI for this task is pending the authorized RC push.

## Release boundary

The immutable context-band result remains 0.6667 against the unchanged 0.90
gate. This schema-parity work does not make PR #16 promotable.
