# TASK-037 — Rust annotation pack operations

## Contract covered

Ported all public functions from `agentrouter.annotation.packs`: per-seed
blinded ordering, labelled IDs, pending candidates, label-free progress,
merge-by-candidate, disagreement selection, blinded adjudication candidates,
and CSV export.

CPython's integer seed expansion and MT19937 shuffle are reproduced, including
negative and arbitrary-width decimal seeds. Merge order follows first
appearance and appends labels in annotator input order. CSV uses Python's
quoting, boolean, float, and CRLF conventions.

## Differential evidence

- Eight focused Python/Rust tests pass: six shuffle seeds (zero, positive,
  negative, and multiword values through 80 bits), pending/progress behavior,
  merge ordering, disagreement/adjudication filtering, blinding, and CSV fields
  containing commas and quotes plus integer and scientific-notation confidence.
- Evaluation crate tests, workspace Clippy, Rust format, Ruff, and diff checks
  pass locally.
- The parity matrix marks `agentrouter/annotation/packs.py` **Parity** based on
  differential coverage for each public operation.
