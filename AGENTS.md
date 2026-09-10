# AgentRouter OS - Codex Operating Contract

## Mission

Build AgentRouter OS as a local-first, explainable model and execution-host routing platform
with safe CLI, API, SDK, MCP, plugin, evaluation, and release surfaces. Prefer honest measured
evidence over optimistic status. Resume automatically from `LOOP_STATE.json`; do not restart
completed work without first reproducing it.

## Invariants

- Keep task classification, policy filtering, model ranking, host resolution, execution planning,
  and safety gating as distinct layers. Model facts come from validated registries, not engine
  special cases. CLI, REST, MCP, and SDKs must share authoritative business logic and contracts.
- The default product is local, offline-capable, private, and silent. Never log raw prompts,
  generated prompts, credentials, or secret values. Optional telemetry must stay opt-in.
- Remote execution is disabled by default. MCP exposes no execution tool. High-risk tasks and
  non-auto approval states must never auto-execute. Subprocesses use argv with `shell=False`.
- Fail closed on unknown controls, malformed registries, unsafe paths, auth failures, policy
  violations, and ambiguous release evidence. Preserve Python 3.10-3.13 and Windows/Linux support.
- Preserve `.claude/` as historical/reference material, but do not assume its hooks, agents, or
  skills run in Codex. Put deterministic protections in tests, CI, scripts, and this file.

## Mandatory reading order

Before behavior changes, read: `AGENTS.md`, `CODEX_HANDOFF.md`, `LOOP_STATE.json`, `LOOP_LOG.md`,
`loop/BACKLOG.yaml`, `loop/QUALITY_GATES.yaml`, the latest `loop/handoffs/` file, the current task
directory, `README.md`, `command.md`, architecture/security/testing/release docs, `pyproject.toml`,
all workflows, then the affected production modules and tests. Treat checkboxes and past summaries
as leads until current commands reproduce them.

## Engineering loop

For each task: DISCOVER -> BASELINE -> PLAN -> TEST CONTRACT -> IMPLEMENT -> FOCUSED VERIFY ->
INDEPENDENT AUDIT -> SECURITY REVIEW -> CUSTOMER REVIEW -> ROOT-CAUSE REPAIR -> FULL REGRESSION ->
RELEASE CHECK -> RECORD -> COMMIT -> PUSH TO THE CURRENT NON-MAIN BRANCH -> INSPECT CI -> REPAIR ->
NEXT TASK. The implementer must not be the only reviewer. Keep agents/worktrees few and give them
non-overlapping ownership.

After each completed task update `LOOP_STATE.json`, `LOOP_LOG.md`, `CODEX_HANDOFF.md`,
`QUALITY_DASHBOARD.md`, `RELEASE_READINESS.md`, `PRODUCT_ACCEPTANCE.md`, `KNOWN_LIMITATIONS.md`, and
the task evidence directory. Never lower a threshold or weaken a test merely to obtain a pass.

## Verification commands

Use the repository virtual environment when valid and lockfile-respecting Node installs:

```console
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest .claude/hooks/test_hooks.py -q
.venv\Scripts\python.exe -m pytest --cov=agentrouter --cov-branch
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m bandit -c pyproject.toml -r agentrouter
.venv\Scripts\python.exe -m pip_audit -r requirements.txt
.venv\Scripts\python.exe -m agentrouter eval run --all
.venv\Scripts\python.exe -m build
cd sdk/typescript && npm ci && npm test && npm run typecheck
```

Also build wheel and sdist, install the wheel into a fresh venv, change to a directory outside the
repository, and smoke-test imports, setup/init, routing, registries, hosts, evaluation, packaged
resources, API, MCP, and plugins. Validate workflow YAML and inspect GitHub checks after every push.

## Release gates

Mandatory tests and supported-platform jobs must pass without silent skips; Ruff/format/type checks
must be green; Bandit, dependency audit, and secret scan must be clean or explicitly mitigated;
wheel/sdist and clean-wheel smoke must pass; all seven evaluation gates must pass; selected critical
module mutation score must be >=85%, safety/policy/execution modules >=95%, with no safety/auth/policy
bypass survivor. A tool crash is a failed mutation run, never a passing score. Public-beta and
production claims additionally require the evidence listed in `loop/QUALITY_GATES.yaml` and
`RELEASE_READINESS.md`.

## Git and autonomy policy

Preserve inherited staged, unstaged, and untracked work. Never use `git reset --hard`, `git clean`,
`git checkout --`, `git restore`, `git stash`, destructive rebase, history rewriting, or branch
deletion. Inspect exact diffs before staging. Never commit generated/local/sensitive files.

Current owner authorization permits commits and pushes only to
`release/agentrouter-v0.5-rc1`. Never push directly to `main`; never merge, tag, publish, create a
release, deploy, enable paid services, or alter production infrastructure without fresh owner
authorization. Reversible, local, no-cost, credential-free, compatibility-preserving, testable
engineering decisions may be made autonomously.

Ask the owner only for credentials, paid inference/services, infrastructure provisioning,
destructive migration, main merge, tags/releases, PyPI or marketplace publication, production
deployment, legal/licensing decisions, irreversible product-direction conflicts, or pushing the
release-candidate branch while a mandatory gate is failing.

Routine, reversible, local, no-cost work never requires owner confirmation. The loop continues
automatically to the next task whenever BOTH hold: (a) another locally actionable task exists, and
(b) that task needs no money, credentials, deployment, destructive operation, merge, release, or
public push. Do not stop after a single task or after analysis; only stop at a genuine terminal
state (see below) or when the sole remaining work needs one of the owner-gated items above.

## Terminal states and reporting

Use `IN_PROGRESS` while local code, tests, audit, docs, CI, or repair work remains.
`BLOCKED_EXTERNAL` requires credentials, paid services, infrastructure, approvals, or real users;
`BLOCKED_USER` requires an irreversible owner decision; `CONTEXT_HANDOFF` requires exact resumable
state. `PUBLIC_BETA_READY` and `PRODUCTION_READY` require every named gate and current evidence.

Before any stop, record the branch/HEAD, exact files changed, tests and results, failures, GitHub
check state, next command, next task, and files that must not be discarded in `CODEX_HANDOFF.md`.

