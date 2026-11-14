# TASK-038 — Rust annotation artifact store

## Contract covered

Ported candidate and dataset YAML persistence, per-item annotation JSONL,
manifest JSON persistence, and the canonical split SHA-256. Writers create
parent directories. Dataset output and hashing sort items by ID; canonical
JSON recursively sorts keys, excludes nulls, uses compact separators, and
escapes Unicode as Python's `json.dumps` does.

## Differential evidence

- Four focused Rust/Python file and hash cases pass in both directions for
  candidates, labels, datasets, and manifests.
- JSONL bytes and sorted/indented manifest JSON bytes match exactly, including
  Unicode escaping. The SHA fixture verifies item ordering and Unicode prompts.
- Rust evaluation crate tests pass; complete workspace/Clippy/format/Ruff and
  hosted cross-platform checks are being run for the next push.
- `agentrouter/annotation/store.py` is marked **Parity** in the 77-module
  inventory.
