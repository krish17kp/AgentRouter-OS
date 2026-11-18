# TASK-039 — Rust annotation candidate generation

## Contract covered

Ported the stable interleaved 63-prompt bank and deterministic unlabelled
candidate generation. Seeded shuffle reuses the verified CPython-compatible
integer seed expansion and MT19937 implementation from annotation packs.
Candidate IDs, category, source, prompt, template scope, count handling, and
negative Python slice counts match the Python module.

## Differential evidence

- Fifty Python/Rust generation cases pass across five seeds (zero, positive,
  negative, 40-bit, and 80-bit) and ten counts (None, zero, positive, larger
  than bank, and negative slicing).
- One additional differential verifies the exact 63-record bank and its stable
  interleaved order.
- Evaluation workspace, Clippy, Rust format, Ruff, and full Python regression
  pass for the complete TASK-038/039 increment locally; hosted cross-platform CI starts after push.
- `agentrouter/annotation/candidates.py` is marked **Parity** in the inventory.
