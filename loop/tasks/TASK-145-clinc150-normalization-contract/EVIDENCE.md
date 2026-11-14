# TASK-145 evidence

Added direct Python/Rust normalization comparisons for the CLINC150
`_load_real` row transformation. The fixtures cover all eleven ordered intent
hints, unknown intents, `oos`, a label string matching two hints, Unicode task
text, source-row IDs, repeated lowercase utterances, and punctuation-only
normalized-hash duplicates. Comparison includes every serialized
`EvaluationCase` field after Python's shared real-mode deduplication.

## Local verification

- `./.venv/bin/python -m pytest -q tests/test_rust_clinc150_compat.py`: 3 passed.
- External dataset access is stubbed; no network request occurs.
- Rust CLI compilation and execution are part of the differential tests.

The Rust transformation matches the tested Python behavior. The parity matrix
remains Partial because the Python module's external Hugging Face dataset
loading path has no Rust-equivalent loader contract.
The differential was pushed at `d80a6df`; hosted validation is pending.
