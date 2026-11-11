# TASK-040 — Rust annotation strategy comparison

## Contract covered

Ported `agentrouter.annotation.compare` prediction and reporting for the rules,
learned, and hybrid strategies. The report includes filtered labelled-item
counts, abstentions, macro-F1, per-band recall, accuracy, seeded 95% bootstrap
intervals, ECE, and rules fallback rate. The Python-compatible MT19937 stream
used by `random.Random(seed).randrange()` is shared with the annotation pack
port. The implementation is measurement-only and leaves the frozen release
gate unchanged.

## Differential evidence

- Five Python/Rust cases compare all strategy report fields, covering all three
  bands, an abstained item, a band with support, threshold edge values, and
  seeded bootstrap sampling.
- Focused annotation compare/store checks: 9 passed.
- Full workspace tests, Clippy, formatting, Ruff, and full Python coverage run
  are in progress before commit/push.
- `agentrouter/annotation/compare.py` is marked **Parity** in the inventory.
