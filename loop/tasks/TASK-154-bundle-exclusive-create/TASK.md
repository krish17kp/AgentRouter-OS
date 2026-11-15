# TASK-154 — Exclusive diagnostic artifact creation

Baseline: Python bundle._write replaces an existing artifact. Rust create_new rejects it.
Prepared patch is held outside the repository at
/home/krish/.codex/agentrouter-recovery/task154.patch until TASK-153 regression completes.
Use binary exclusive creation and normalize collisions to BundleError. Test existing
JSON/text, live/dangling symlinks, and final-path insertion immediately before open.
This does not claim to solve parent-directory replacement races.
