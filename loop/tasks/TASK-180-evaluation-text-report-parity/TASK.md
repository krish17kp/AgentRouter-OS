# TASK-180 — Context-band CLI text parity

## Contract

The Rust `agentrouter-evaluate context-band-generalization` human-readable
output must preserve Python's visible evidence: confidence intervals, Python
container formatting, and a signed four-decimal accuracy delta.

## Scope

- include the bootstrap confidence interval for macro-F1;
- render confidence intervals and per-band recall with Python-compatible `repr`;
- avoid quoting the holdout checksum;
- format the accuracy delta with an explicit sign and four decimals.

JSON output remains unchanged and is still the machine-readable contract.
