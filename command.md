# AGENTROUTER OS — GRAPH-AWARE MARKET-GRADE PRODUCTION LOOP

#

# You are taking over an existing advanced codebase. Do not treat this as a

# greenfield project and do not trust old completion claims without reproducing

# them.

#

# Repository:

# D:\Krish\Agentrouteros

#

# Product:

# AgentRouter OS — a universal AI model-routing platform that classifies tasks,

# selects the best model, chooses an available execution host, explains the

# decision, enforces safety and policy, tracks quality/cost/latency, and exposes

# CLI, API, SDK, MCP and coding-assistant integrations.

#

# Ultimate goal:

# Turn the current strong local engineering foundation into a complete,

# customer-friendly, benchmark-proven, distributable and operationally reliable

# product comparable in quality and usability to major developer tools.

#

# Use Graphify actively as the repository knowledge and impact-analysis layer.

# Use the existing production loop as the execution, testing, audit and repair

# layer.

#

# Do not stop after writing a plan.

======================================================================

1. # PRESERVE THE COMPLETE CURRENT WORK

The working tree contains valuable uncommitted work from earlier Claude
sessions.

Before editing:

- inspect the current branch;
- inspect HEAD and remotes;
- inspect staged files;
- inspect unstaged files;
- inspect untracked and ignored files;
- identify generated files;
- identify sensitive files;
- record the complete state.

Run:

git status --short --branch
git rev-parse HEAD
git remote -v
git diff --check
git diff --stat
git diff --cached --check
git diff --cached --stat
git ls-files --others --exclude-standard

Never run:

- git reset --hard;
- git clean;
- destructive restore/checkout commands;
- force push;
- history rewriting;
- deletion of inherited work.

The current working tree is more complete than the remote repository.

Create or refresh:

PROJECT_STATUS.md
CODEX_HANDOFF.md, if present
LOOP_STATE.json
LOOP_LOG.md

The project status must be IN_PROGRESS while any locally actionable task
remains.

====================================================================== 2. RECONSTRUCT THE PROJECT
======================================================================

Read all durable project context before editing:

- CLAUDE.md
- AGENTS.md
- command.md
- README.md
- LOOP_STATE.json
- LOOP_LOG.md
- loop/README.md
- loop/BACKLOG.yaml
- loop/QUALITY_GATES.yaml
- loop/PRODUCT_SCENARIOS.yaml
- latest loop/reports/audit-\*/report.md
- latest loop/handoffs/\*
- all loop/tasks/\*
- QUALITY_DASHBOARD.md
- PRODUCTION_READINESS.md
- RELEASE_READINESS.md
- PRODUCT_MASTER_PLAN.md
- PRODUCT_ACCEPTANCE.md
- ARCHITECTURE.md
- ARCHITECTURE_DECISIONS.md
- SECURITY.md
- TESTING.md
- KNOWN_LIMITATIONS.md
- CHANGELOG.md
- UPGRADING.md
- RELEASE.md
- pyproject.toml
- all production modules
- all tests
- all SDK, MCP and plugin files
- every GitHub workflow
- all .claude agents, skills, hooks and settings

Do not use previous summaries as evidence. Reproduce the actual state.

Create:

MARKET_READINESS.md
PRODUCT_GAP_ANALYSIS.md
PRODUCTION_ROADMAP.md

These must distinguish:

- implemented;
- partially implemented;
- locally testable;
- externally blocked;
- owner decision;
- customer validation required;
- production-only requirement.

====================================================================== 3. VERIFY THE OFFICIAL GRAPHIFY INSTALLATION
======================================================================

The official package must be `graphifyy`; the command is `graphify`.

Verify:

python -m pip show graphifyy
python -m pip show graphify
where graphify
graphify --version

Do not execute an unrelated similarly named package.

When the official package is absent, install `graphifyy` using an isolated tool
environment where possible.

Do not modify the AgentRouter package dependencies merely to install a
development assistant tool.

Record:

- Graphify package identity;
- version;
- executable path;
- installation scope;
- package provenance.

====================================================================== 4. INSTALL GRAPHIFY SAFELY FOR THIS PROJECT
======================================================================

Inspect the existing:

- .claude/settings.json
- .claude/settings.local.json
- .claude/skills/
- .claude/hooks/
- CLAUDE.md
- AGENTS.md

Graphify must not overwrite or disable the existing production-loop hooks,
skills, agents or safety restrictions.

Install it project-locally using the official Claude integration only after
taking a diffable backup or recording the current files:

graphify claude install --project

Inspect every file Graphify adds or modifies.

Merge configurations instead of replacing existing configuration.

Do not install globally when project-local installation is sufficient.

Do not grant Graphify access to:

- .env;
- secrets;
- credentials;
- virtual environments;
- build output;
- caches;
- local databases;
- node_modules;
- generated benchmark artifacts;
- Git internals.

Add appropriate exclusions to .gitignore and .claudeignore.

Always exclude graphify-out/ from Claude prompt-cache scanning through
.claudeignore.

Decide whether GRAPH_REPORT.md and graph.json should be version-controlled
based on size, stability and security. Never commit caches, graph.html or large
generated output automatically.

Document the chosen policy in:

docs/GRAPHIFY.md

====================================================================== 5. BUILD THE INITIAL KNOWLEDGE GRAPH
======================================================================

Create a clean code graph first.

Use a code-only/local extraction first where supported.

Then, after confirming secret and generated-file exclusions, build the complete
project graph through the Claude skill:

/graphify . --mode deep

Expected outputs include:

graphify-out/graph.json
graphify-out/GRAPH_REPORT.md
graphify-out/graph.html

Verify:

- the graph is not empty;
- production modules are represented;
- CLI, API, SDK, MCP and evaluation components appear;
- calls/imports/inheritance relationships exist;
- architecture communities are meaningful;
- generated/cache directories are absent;
- secrets are absent;
- paths are valid;
- graph queries return source locations.

Record a baseline:

docs/GRAPHIFY_BASELINE.md

Include:

- node count;
- edge count;
- detected communities;
- highest-connectivity nodes;
- surprising cross-module connections;
- suspected architecture hotspots;
- ambiguous/inferred edges requiring verification;
- known limitations.

Never treat an inferred Graphify edge as verified production truth without
checking the source.

====================================================================== 6. USE GRAPHIFY ACTIVELY, NOT DECORATIVELY
======================================================================

Before broad grep or reading many files, query the graph.

For every task, create:

loop/tasks/<TASK>/graph-discovery.md
loop/tasks/<TASK>/graph-impact-before.md
loop/tasks/<TASK>/graph-impact-after.md

Before implementation, use commands equivalent to:

graphify query "<which components participate in this feature?>"
graphify query "<what depends on the component being changed?>"
graphify path "<source component>" "<target component>"
graphify explain "<main component>"

Use the actual graph node names discovered in the repository.

Before changing any shared module, identify:

- callers;
- imports;
- reverse dependencies;
- public interfaces;
- tests;
- persistence boundaries;
- security boundaries;
- execution paths;
- documentation references;
- SDK/API/plugin consumers.

After each completed task:

/graphify . --update

Then query the changed subsystem again.

Compare before and after:

- new dependencies;
- removed dependencies;
- unexpected cross-community edges;
- increased coupling;
- newly created god nodes;
- duplicated execution paths;
- architecture layering violations;
- unreachable or orphaned components.

Graphify findings must influence planning, testing and audit scope.

Every five completed tasks, or after a major architecture change, perform a
full deep rebuild instead of only an update.

Use Graphify PR-impact and conflict analysis after release-candidate branches
and pull requests exist.

====================================================================== 7. CURRENT REPORTED BASELINE — REPRODUCE IT
======================================================================

Previous sessions reported:

- 426 Python tests passed;
- one environment-only OpenTelemetry skip;
- TypeScript SDK tests passed;
- hook tests passed;
- Ruff and formatting clean;
- Bandit clean;
- local evaluation 98.32/100;
- seven local evaluation gates passed;
- clean-wheel evaluation worked outside the repository;
- four independent product reviewers passed;
- benchmark resources were moved into the package;
- API, Python SDK, TypeScript SDK and MCP exist;
- rate limiting and idempotency exist;
- structured logging and optional OpenTelemetry exist;
- plugin installation exists;
- SBOM and SLSA release workflow exist.

Reproduce all of this.

Run:

python -m pytest -q
python -m pytest .claude/hooks/test_hooks.py -q
ruff check .
ruff format --check .
bandit -c pyproject.toml -r agentrouter
pip-audit -r requirements.txt
python -m agentrouter eval run --all
python -m build

Run the TypeScript SDK using its actual lockfile and package scripts.

Build a wheel and install it into a clean temporary virtual environment.

Change to a directory outside the repository and verify:

- import;
- --help;
- init;
- setup;
- model listing;
- host listing;
- route;
- evaluation;
- MCP optional import;
- server optional import;
- packaged data;
- plugin resources.

Create:

loop/baselines/market-grade-restart-<date>.md

====================================================================== 8. COMPLETE THE REMAINING LOCAL AUDIT TICKETS
======================================================================

Complete these before claiming local release readiness.

TASK-008 — plugin uninstall cleanup:

- remove AgentRouter-created files;
- remove an integration directory only when empty;
- preserve unrelated user files;
- preserve non-empty parent directories;
- prevent path traversal;
- handle symlinks/junctions safely;
- make uninstall idempotent;
- verify reinstall;
- test Windows and POSIX behavior;
- document complete removal and data-purge behavior.

TASK-009 — held-out benchmark generalization:

- separate development cases from final holdout cases;
- detect exact and near-duplicate prompts;
- add unseen vocabulary and sentence structures;
- include adversarial near-neighbor prompts;
- do not tune directly against the final holdout;
- report accuracy, macro-F1 and per-band recall;
- compare old and new behavior;
- preserve the other release gates;
- do not manipulate cases to retain the previous score;
- document the true result even when lower.

TASK-010 — Linux mutation CI:

- run mutation testing in GitHub Actions Linux;
- begin with safety, policy, execution, controls, hosts and server limits;
- fail clearly when the mutation tool crashes;
- upload reports;
- enforce no surviving safety/auth/policy bypass mutants;
- target >=95% for critical safety/policy modules;
- target >=85% for the selected broader set;
- add tests for meaningful survivors;
- do not install or modify WSL locally.

====================================================================== 9. DEFINE THE COMPLETE MARKET-GRADE PRODUCT
======================================================================

Do not continue building random features.

First determine exactly what AgentRouter OS must become.

Create or refresh:

PRODUCT_VISION.md
TARGET_USERS.md
CUSTOMER_JOURNEYS.md
COMPETITIVE_ANALYSIS.md
PRICING_AND_DISTRIBUTION_OPTIONS.md
MARKET_REQUIREMENTS.md
PRODUCT_NON_GOALS.md

Define primary users such as:

- individual developers using multiple AI coding tools;
- engineering teams controlling AI model cost and quality;
- platform teams governing approved providers;
- enterprises requiring auditability and privacy;
- agent builders requiring routing through API/SDK/MCP.

Define the core promise in one sentence.

Define the three strongest customer problems.

Define measurable outcomes:

- quality improvement;
- cost savings;
- latency reduction;
- fewer routing mistakes;
- safer execution;
- easier provider switching;
- clear route explanations;
- fast onboarding.

Do not imitate competitors blindly.

Research current routing products, model gateways, observability products,
coding-assistant plugins and agent platforms using current reliable sources.

Record sources, access dates and verified comparisons.

Do not copy protected code or branding.

====================================================================== 10. PRODUCTION ROADMAP
======================================================================

Build the roadmap in this order unless repository evidence justifies a change.

PHASE A — Preserve and publish the audited engineering foundation

- complete TASK-008, TASK-009 and TASK-010;
- run the complete audit;
- create release/agentrouter-v0.5-rc1;
- commit all valid inherited work;
- exclude secrets and generated files;
- push only the release-candidate branch;
- repair GitHub CI until green;
- do not merge to main without owner approval.

PHASE B — Trusted live model catalog

- official provider adapters;
- exact model IDs;
- pricing;
- context/output limits;
- modality and tool support;
- release/deprecation state;
- provenance and retrieval date;
- atomic refresh;
- stale-data warnings;
- rollback;
- offline fallback;
- schema migrations.

PHASE C — Verified host access

- distinguish installed/configured/authenticated/authorized/degraded;
- opt-in live checks;
- timeout and rate-limit handling;
- no secret exposure;
- deterministic offline behavior;
- fail-safe execution.

PHASE D — Measured routing intelligence

- real quality, cost, latency and failure data;
- benchmark-measured model profiles;
- public development benchmarks;
- private unseen holdout;
- random, cheapest, strongest and best-single-model baselines;
- oracle regret;
- quality per dollar;
- under-routing;
- unnecessary frontier use;
- abstention;
- confidence calibration.

PHASE E — Excellent customer experience

- one-command install;
- five-minute first successful route;
- guided setup;
- provider diagnostics;
- understandable explanations;
- clear recovery actions;
- accessible/no-color output;
- Windows, macOS and Linux documentation;
- configuration examples;
- upgrade and uninstall;
- privacy explanation;
- cost controls;
- telemetry opt-in only.

PHASE F — Complete developer platform

- stable CLI;
- versioned REST API;
- Python SDK;
- TypeScript SDK;
- MCP;
- Claude Code integration;
- Codex integration;
- additional IDE integrations;
- generated examples;
- compatibility policy;
- plugin manifest and validation system.

PHASE G — Team and hosted architecture

- PostgreSQL path;
- tenant isolation;
- organizations and projects;
- RBAC;
- API keys;
- audit logs;
- usage quotas;
- policy administration;
- retention and deletion;
- export;
- optional hosted control plane;
- local/private execution by default.

Do not deploy without owner approval.

PHASE H — Reliability, security and governance

- SLOs;
- structured logs;
- metrics and traces;
- load tests;
- graceful degradation;
- backup and restore;
- disaster recovery;
- incident response;
- threat model;
- dependency and secret scanning;
- SBOM;
- provenance;
- privacy policy;
- data processing inventory;
- security reporting process.

PHASE I — Distribution and adoption

- PyPI release;
- signed GitHub release;
- installation scripts;
- official documentation site;
- tutorials;
- example projects;
- architecture diagrams;
- comparison pages;
- contributor guide;
- issue templates;
- release notes;
- plugin marketplace packages;
- community feedback process.

Publishing requires owner approval.

PHASE J — Private and public beta

- recruit real users;
- onboarding funnel;
- task success measurement;
- route satisfaction feedback;
- cost and latency measurement;
- failure analysis;
- support process;
- changelog discipline;
- beta exit criteria.

Real user evidence is mandatory before production-ready status.

====================================================================== 11. GRAPHIFY AS A POSSIBLE PRODUCT INTEGRATION
======================================================================

Research, but do not force, a first-party AgentRouter–Graphify integration.

Potential uses:

- use Graphify impact context as an optional classifier signal;
- estimate context requirements from affected graph size;
- identify tool requirements from the dependency path;
- provide graph-aware route explanations;
- route Graphify semantic extraction to an appropriate model;
- estimate change risk from dependency reach;
- show affected communities before execution.

Build this only behind an experimental feature flag after:

- architecture review;
- privacy review;
- latency measurement;
- benchmark comparison;
- no-Graphify fallback;
- proof that it improves routing.

Do not make AgentRouter depend on Graphify for basic operation.

Graphify remains an optional development and context enhancement.

====================================================================== 12. PERMANENT GRAPH-AWARE LOOP
======================================================================

For every current and future task:

1. INTAKE
2. GRAPH DISCOVERY
3. SOURCE VERIFICATION
4. BASELINE
5. ARCHITECTURE REVIEW
6. ACCEPTANCE CONTRACT
7. TEST CONTRACT
8. IMPLEMENTATION
9. FOCUSED VERIFICATION
10. GRAPH UPDATE
11. GRAPH IMPACT REVIEW
12. INDEPENDENT VERIFICATION
13. SECURITY REVIEW
14. CUSTOMER REVIEW
15. ROOT-CAUSE REPAIR
16. FULL REGRESSION
17. CLEAN-PACKAGE VERIFICATION
18. RELEASE CHECK
19. STATE RECORDING
20. COMMIT TO NON-MAIN BRANCH
21. PUSH
22. CI INSPECTION
23. CI REPAIR
24. NEXT TASK

The implementer must not be the only reviewer.

Use existing focused subagents where available:

- repo explorer;
- graph/architecture reviewer;
- implementation engineer;
- verification engineer;
- security reviewer;
- customer advocate;
- release auditor;
- product/market reviewer.

Use parallel agents only when files do not overlap.

====================================================================== 13. QUALITY AND RELEASE GATES
======================================================================

A task is complete only when:

- all acceptance requirements have evidence;
- meaningful tests pass;
- negative and failure paths pass;
- graph impact is reviewed;
- security review passes;
- customer review passes;
- documentation is accurate;
- package behavior works;
- compatibility is preserved;
- state files are updated.

Production gates include:

- zero critical/high security findings;
- all mandatory CI green;
- no silently skipped mandatory jobs;
- clean wheel and sdist;
- Windows/Linux/macOS support evidence as declared;
- Python-version matrix green;
- SDK contract tests;
- plugin install/upgrade/uninstall;
- API compatibility;
- MCP safety;
- mutation gates;
- private holdout;
- real provider evidence;
- real-user beta evidence;
- backup/restore;
- rollback;
- incident runbook;
- privacy controls.

Do not call a local fixture score production proof.

Do not lower gates merely to pass.

Do not add weak tests solely to increase coverage.

====================================================================== 14. AUTONOMY AND SAFETY
======================================================================

Operate autonomously for reversible local engineering work.

Do not ask routine questions. Routine, reversible, local, no-cost, credential-free tasks never
require owner confirmation.

Continue the loop automatically to the next task whenever BOTH hold:

- another locally actionable task exists;
- no money, credentials, deployment, destructive operation, merge, release, or public push is
  required.

Ask the owner only for: pushing the release-candidate branch while a mandatory gate is failing;
merge to main; publication, deployment, paid inference, credentials; or destructive changes.
Do not stop after one task or after analysis; stop only at a genuine terminal state or when the
sole remaining work is owner-gated or externally blocked.

You may:

- inspect;
- edit;
- test;
- install declared development dependencies;
- create non-main branches;
- commit verified work;
- push to the current release/task branch;
- repair CI failures;
- update graph and documentation.

You may not, without owner approval:

- push directly to main;
- merge;
- force push;
- tag;
- publish to PyPI;
- publish to marketplaces;
- deploy;
- provision paid infrastructure;
- use paid inference;
- delete user data;
- expose credentials;
- perform destructive migrations;
- change licensing;
- make irreversible product decisions.

Never use bypass-permissions mode.

====================================================================== 15. PERSISTENT STATE
======================================================================

Every session must resume from repository state rather than chat memory.

Maintain:

LOOP_STATE.json
LOOP_LOG.md
PROJECT_STATUS.md
CODEX_HANDOFF.md
QUALITY_DASHBOARD.md
MARKET_READINESS.md
PRODUCTION_READINESS.md
RELEASE_READINESS.md
KNOWN_LIMITATIONS.md
docs/GRAPHIFY.md
docs/GRAPHIFY_BASELINE.md

Before context exhaustion, write:

- current task;
- branch;
- commits;
- changed files;
- Graphify queries used;
- graph updates;
- tests run;
- failures;
- CI state;
- remaining findings;
- next exact command;
- next task.

====================================================================== 16. BEGIN NOW
======================================================================

Start immediately:

1. preserve the complete working tree;
2. reconstruct actual project state;
3. verify the official Graphify package;
4. safely install the project-local Graphify Claude integration;
5. build and validate the knowledge graph;
6. reproduce the full local baseline;
7. complete TASK-008;
8. complete TASK-009;
9. implement TASK-010 Linux mutation CI;
10. run the full graph-aware product audit;
11. create release/agentrouter-v0.5-rc1;
12. commit all verified inherited work;
13. push the release-candidate branch;
14. inspect and repair every GitHub check;
15. build the market-grade roadmap;
16. continue automatically through the highest-priority locally actionable
    tasks.

Do not stop after analysis or planning.

Stop only at:

- PUBLIC_BETA_READY;
- PRODUCTION_READY;
- genuine BLOCKED_EXTERNAL;
- genuine BLOCKED_USER;
- UNSAFE;
- ENVIRONMENT_FAILURE;
- CONTEXT_HANDOFF.

Do not claim production readiness without real provider, private holdout,
operational and real-user evidence.
