---
name: release-check
description: Final release-gate decision for AgentRouter OS. Use when the user asks "is this release-ready", "run release check", or before tagging/publishing. Traces every acceptance criterion to reproduced evidence against loop/QUALITY_GATES.yaml.
context: fork
---

# Release Check

1. Load `loop/QUALITY_GATES.yaml` and the task acceptance criteria.
2. Delegate to `release-auditor`. For each gate, reproduce the proving command:
   - `python -m pytest -q` (all green, no silent skips)
   - `ruff check` + `ruff format --check`
   - `bandit -c pyproject.toml -r agentrouter` + `pip-audit`
   - `agentrouter eval run --all`
   - `python -m build` + install wheel in a clean env + `agentrouter --help`
3. Map requirement → impl (file:line) → test → command output → docs.
4. Verdict per gate: PASS / FAIL / BLOCKED with the exact reason.
5. Write the decision to the task `release-check.md` and update
   `RELEASE_READINESS.md` / `PRODUCTION_READINESS.md`.

Never report release-ready while any mandatory gate FAILs or lacks current
evidence. Known non-blocking open gates must be listed explicitly.
