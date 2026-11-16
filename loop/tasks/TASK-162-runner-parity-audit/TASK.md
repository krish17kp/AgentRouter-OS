# TASK-162 — Evaluation runner full-module parity audit

Audit every public and observable behavior in `agentrouter.evaluation.runner`
against the Rust registered runner: default/profile/dataset selection, sampling,
MASSIVE language filtering, fixture and real-source blockers, both grading
modes, context generalization, provenance/environment fields, git/code identity,
dataset quality, error ordering, and malformed options. Promote the row only
when the complete stable report contract and fail-closed paths are measured.
