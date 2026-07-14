# AGENTROUTER OS — PRODUCTION PLATFORM LOOP

#

# Build AgentRouter OS as a large-scale, widely adopted routing platform,

# plugin ecosystem, skill, SDK and hosted/local product.

#

# This is a LOOP-ENGINEERING assignment.

# Do not treat it as a one-session feature request.

#

# Continue working through bounded implementation loops until every locally

# actionable acceptance criterion is complete and verified.

#

# Repository:

# D:\Krish\Agentrouteros

# https://github.com/krish17kp/AgentRouter-OS

# ====================================================================== 0. PRODUCT MINDSET

AgentRouter OS is not merely a command that prints a model recommendation.

The intended product is:

1. A universal model-routing decision engine.
2. A universal agent-host routing layer.
3. A Claude Code / Codex / IDE-installable skill or plugin.
4. A local-first CLI for individual developers.
5. A REST API and SDK for applications.
6. A governed team platform.
7. A benchmark and model-intelligence laboratory.
8. A trusted model catalog with provenance and measured performance.
9. An execution gateway with strict safety controls.
10. An open ecosystem that other developers can extend.

The long-term user experience should be:

    install AgentRouter
    run one onboarding command
    discover locally available agent hosts and credentials
    submit a task
    receive the exact recommended model and execution host
    understand the reason, quality, price, latency and risk
    execute safely or export the generated prompt
    submit feedback
    improve future routes
    use AgentRouter inside Claude Code, Codex, Cursor, IDEs and applications

The project should eventually be able to support:

    agentrouter route "<task>"
    agentrouter run "<task>"
    agentrouter models refresh --all
    agentrouter hosts doctor
    agentrouter explain <decision>
    agentrouter eval run --profile release
    agentrouter server
    agentrouter plugin install claude-code
    agentrouter plugin install codex
    agentrouter config wizard

Do not build isolated features without connecting them to this product vision.

======================================================================

1. # OPERATING RULES

Read these files before making changes:

- CLAUDE.md
- command.md
- README.md
- PRD.md
- BRD.md
- ARCHITECTURE.md
- ROUTING_RULES.md
- MODEL_REGISTRY_SCHEMA.md
- PROVIDER_ADAPTER_SPEC.md
- CLI_SPEC.md
- TESTING.md
- SECURITY.md
- ROADMAP.md
- MILESTONES.md
- TODO.md
- CHANGELOG.md
- EVALUATION_STATUS.md
- EVALUATION_ACCEPTANCE.md
- EVALUATION_HANDOFF.md
- pyproject.toml
- all files under agentrouter/
- all files under tests/
- all GitHub Actions workflows
- all integration/plugin/skill files

Git restrictions:

- Do not run git add.
- Do not commit.
- Do not push.
- Do not create tags.
- Do not create pull requests.
- Do not rewrite history.
- The owner will review and perform Git operations manually.

Security restrictions:

- Never use --dangerously-skip-permissions.
- Never use shell=True.
- Never print API-key values.
- Never write secrets into fixtures, reports or logs.
- Never perform paid model inference without explicit approval.
- Never modify production infrastructure.
- Never deploy publicly without explicit approval.
- Never delete user data.
- Never perform destructive migrations.
- Never silently expand the task’s blast radius.

You may:

- inspect files;
- edit project files;
- create tests;
- install development dependencies after explaining them;
- run local tests;
- build packages;
- use mocked provider APIs;
- run safe read-only discovery commands;
- download public evaluation datasets into ignored cache directories;
- create local Docker development files without deploying them.

Do not ask the user routine implementation questions.

Choose sensible, documented defaults and continue.

Ask only when:

- credentials are required;
- money may be spent;
- production infrastructure could change;
- a legal/license decision requires the owner;
- a destructive action is unavoidable;
- two incompatible product directions genuinely require an owner decision.

# ====================================================================== 2. LOOP CONTRACT

Create and maintain these durable memory files:

PRODUCT_MASTER_PLAN.md
LOOP_STATE.json
LOOP_LOG.md
ARCHITECTURE_DECISIONS.md
PRODUCT_ACCEPTANCE.md
RELEASE_READINESS.md
KNOWN_LIMITATIONS.md

LOOP_STATE.json must contain:

{
"loop_version": 1,
"current_phase": "",
"current_objective": "",
"status": "",
"iteration": 0,
"repo_sha_at_start": "",
"completed": [],
"in_progress": [],
"blocked_external": [],
"blocked_user": [],
"failed_verifications": [],
"next_action": "",
"last_test_results": {},
"last_updated": ""
}

Every implementation loop must perform:

1. OBSERVE
   - Read LOOP_STATE.json.
   - Inspect current repository state.
   - Inspect outstanding acceptance items.
   - Run the smallest relevant baseline checks.
   - Identify one coherent vertical slice.

2. PLAN
   - Define the exact slice.
   - Define files expected to change.
   - Define tests before implementation.
   - Define rollback and compatibility concerns.
   - Define the verification oracle.

3. IMPLEMENT
   - Build the smallest complete production-grade slice.
   - Avoid placeholder-only implementations.
   - Avoid unrelated refactors.
   - Preserve backward compatibility.
   - Add documentation with the feature.

4. VERIFY
   - Run focused tests.
   - Run static checks.
   - Run integration or CLI smoke checks.
   - Test failure paths.
   - Test backward compatibility.
   - Inspect output as a real user would.

5. ADVERSARIAL REVIEW
   - Use an independent reviewer subagent when useful.
   - The reviewer must search for:
     - silent fallbacks;
     - misleading success claims;
     - security regressions;
     - shell injection;
     - model/provider confusion;
     - stale metadata;
     - race conditions;
     - data leakage;
     - broken Windows behavior;
     - broken packaging;
     - insufficient tests;
     - documentation that overstates completion.

6. REPAIR
   - Fix genuine issues found by tests or review.
   - Do not weaken assertions merely to make tests pass.
   - Add permanent regression tests.

7. RECORD
   - Update LOOP_STATE.json.
   - Append to LOOP_LOG.md.
   - Update PRODUCT_ACCEPTANCE.md.
   - Update KNOWN_LIMITATIONS.md.
   - Record commands and real outputs.
   - Continue to the next loop automatically.

Do not stop merely because one phase passes.

Continue until reaching one of these terminal states:

COMPLETE:
All locally actionable production acceptance criteria are satisfied.

BLOCKED_EXTERNAL:
Only credentials, paid services, Docker-heavy external benchmarks, marketplace
approval, legal review or user-owned infrastructure remain.

BLOCKED_USER:
A real owner decision is required and cannot safely be inferred.

UNSAFE:
Continuing would require a destructive or insufficiently scoped operation.

ENVIRONMENT_FAILURE:
The local machine cannot proceed after reasonable diagnosis and documented
fallback attempts.

CONTEXT_HANDOFF:
The session is nearing its limit. Write a complete resumable handoff and stop.

When using CONTEXT_HANDOFF:

- update every memory file;
- include exact current failing command;
- include exact next step;
- include files changed;
- include tests run;
- include a ready-to-paste continuation prompt;
- never claim the whole product is complete.

# ====================================================================== 3. CURRENT GROUNDED STATE

Assignment A has implemented:

- evaluation architecture;
- real/fixture source separation;
- dataset preparation/status commands;
- real loaders for BANKING77, MASSIVE, LongBench v2 and SWE-bench metadata;
- explicit SKIPPED_EXTERNAL behavior;
- evaluation reports and baseline infrastructure.

Assignment B has implemented or partially implemented:

- vendor versus execution-host distinction;
- exact Anthropic and OpenAI model records;
- real display names and model IDs;
- host discovery;
- two-stage model-to-host routing;
- detailed output;
- exact-model dry-run/execution;
- backward-compatible JSON;
- high-risk execution blocking.

Assignment B still has important unfinished work:

- complete dynamic model-catalog refresh;
- Anthropic official catalog adapter;
- Google official catalog adapter;
- proper OpenAI metadata joining;
- full OpenRouter metadata ingestion;
- route-control flags;
- measured benchmark-derived model scoring;
- expanded tool taxonomy;
- complete model/host test matrix;
- stale-catalog behavior;
- preview/stable policy;
- comprehensive old-decision migration testing;
- package-build verification where not yet run.

The evaluation platform also still requires:

- routing evaluator;
- safety evaluator;
- CLI/platform evaluator;
- provider evaluator;
- feedback/storage evaluator;
- performance evaluator;
- larger reviewed AgentRouter benchmark;
- Hypothesis property tests;
- Promptfoo;
- mutation testing;
- Bandit/pip-audit/secret scanning;
- pytest-benchmark;
- DVC;
- MLflow;
- dedicated evaluation/security/mutation workflows.

Do not restart completed work.

Inspect it, verify it and continue from its actual current state.

# ====================================================================== 4. PRODUCT ARCHITECTURE TARGET

Build toward a modular architecture with these layers:

A. TASK INTELLIGENCE

- task classification;
- complexity estimation;
- risk estimation;
- context estimation;
- output-type detection;
- tool requirements;
- ambiguity and confidence;
- clarification requirements;
- policy constraints.

B. MODEL INTELLIGENCE

- exact vendor;
- exact model ID;
- model family;
- stable/preview/experimental status;
- token limits;
- structured-output support;
- tool support;
- modality support;
- pricing;
- latency;
- reliability;
- regional availability;
- deprecation;
- provenance;
- benchmark scores;
- freshness.

C. HOST INTELLIGENCE

- Claude Code;
- Codex CLI;
- Anthropic API;
- OpenAI API;
- Gemini API;
- OpenRouter;
- local runtimes;
- IDE/manual hosts;
- future third-party agent hosts.

Host records must include:

- installation status;
- authentication configuration;
- verified access status;
- exact supported model IDs;
- execution mode;
- sandbox behavior;
- tool abilities;
- version;
- failure reason;
- last verified timestamp.

D. ROUTING ENGINE

Separate:

1. task interpretation;
2. policy filtering;
3. model eligibility;
4. model ranking;
5. fallback model selection;
6. host availability;
7. host ranking;
8. estimated cost;
9. execution plan;
10. safety gate.

E. EXECUTION GATEWAY

- exact model;
- exact host;
- safe argv execution;
- dry-run;
- timeout;
- cancellation;
- streamed output;
- structured result;
- retry policy;
- controlled fallback;
- audit record;
- no silent model switching;
- no high-risk auto-execution.

F. EVALUATION LAB

- public datasets;
- private reviewed gold cases;
- synthetic routing tests;
- model quality outcomes;
- cost-quality evaluation;
- latency evaluation;
- safety evaluation;
- drift detection;
- regression comparison;
- reproducible experiment tracking.

G. PRODUCT SURFACES

- Python library;
- CLI;
- local dashboard;
- REST API;
- Python SDK;
- TypeScript SDK;
- Claude Code skill/plugin;
- Codex/AGENTS integration;
- MCP server where it adds genuine value;
- IDE integrations;
- hosted team product later.

H. GOVERNANCE

- local-first privacy;
- audit logs;
- team policies;
- allow/deny lists;
- maximum-cost policy;
- stable-only policy;
- model/vendor restrictions;
- sensitive-task no-log mode;
- data-retention controls;
- role-based access in hosted mode.

# ====================================================================== 5. EXECUTION ROADMAP

Work through the phases below in order unless repository evidence shows that a
dependency requires a small adjustment.

Do not attempt every phase in one massive unverified edit.

Complete vertical slices and continuously verify them.

---

## PHASE P0 — REPOSITORY TRUTH AND BASELINE

Goal:
Establish a completely honest, reproducible current baseline.

Tasks:

- confirm current Git SHA;
- inspect working tree;
- run existing CI-equivalent checks;
- identify failing GitHub checks if any;
- run package build;
- install the wheel in a clean environment;
- verify route, models, hosts, execute dry-run and evaluation commands;
- document real current features;
- document false or stale claims;
- establish baseline reports.

Required output:

artifacts/production-baseline/
environment.json
tests.txt
coverage.json
route-samples.json
host-status.json
models.json
package-smoke.txt
limitations.md

Acceptance:

- no unexplained failing test;
- no unverified “green” claim;
- no placeholder production model;
- clean wheel installation;
- old decisions remain readable;
- default CLI works offline.

---

## PHASE P1 — COMPLETE REAL MODEL CATALOGS

Goal:
A trusted, current and refreshable catalog.

Implement:

agentrouter models refresh anthropic
agentrouter models refresh openai
agentrouter models refresh google
agentrouter models refresh openrouter
agentrouter models refresh --all
agentrouter models status
agentrouter models verify
agentrouter models diff
agentrouter models export

Requirements:

- use official APIs or official maintained sources;
- retain exact IDs;
- retain release channel;
- retain source and retrieval date;
- retain prices and effective dates;
- retain context/output limits;
- retain supported modalities and parameters;
- mark missing metadata unknown;
- never fabricate missing values;
- use mocked offline tests;
- keep bundled dated offline snapshots;
- manual overrides win;
- refresh is atomic;
- failed refresh never corrupts active catalog;
- show catalog diff before activation;
- stale warnings at configurable ages.

OpenRouter ingestion must not turn price into capability.

OpenAI catalog visibility and capability metadata must be joined explicitly.

Google preview and experimental models must not be silently treated as stable.

Anthropic aliases and pinned snapshots must be distinguished.

---

## PHASE P2 — COMPLETE HOST DISCOVERY AND ACCESS VERIFICATION

Goal:
Know not merely whether a command or environment variable exists, but whether
the model can actually be used.

Availability states:

- unavailable
- configured
- verified
- degraded
- unknown

Commands:

agentrouter hosts list
agentrouter hosts doctor
agentrouter hosts verify
agentrouter hosts verify claude-code
agentrouter hosts verify codex-cli
agentrouter hosts show <host>

Verification must be:

- safe;
- read-only;
- opt-in for network calls;
- timeout-bounded;
- secret-redacted;
- cached with timestamps.

Do not claim verified from `shutil.which` alone.

---

## PHASE P3 — ROUTING CONTROLS, CONFIDENCE AND ABSTENTION

Implement:

--vendor
--exclude-vendor
--model
--host
--exclude-host
--max-price
--max-estimated-cost
--prefer-quality
--prefer-balanced
--prefer-cheap
--prefer-fast
--stable-only
--allow-preview
--available-only
--include-unavailable
--privacy local-only
--context-tokens
--risk
--tool
--no-log

Add:

- confidence;
- alternative interpretation;
- ambiguity reason;
- needs clarification;
- uncertainty threshold.

When confidence is low, AgentRouter should say so.

Do not confidently route an ambiguous request merely to produce an answer.

---

## PHASE P4 — EXPANDED TOOL AND WORKLOAD TAXONOMY

Replace overly broad labels with a versioned taxonomy:

- file-read
- file-edit
- shell
- code-execution
- browser-automation
- web-search
- network-http
- database-read
- database-write
- cloud-read
- cloud-write
- git-read
- git-write
- issue-tracker
- vision
- audio
- structured-output
- function-calling
- long-running-agent
- parallel-subagents

Separate:

- required tools;
- optional tools;
- prohibited tools.

Tool requirements must influence both model and host eligibility.

Backward compatibility must be preserved for old `web`, `shell` and
`file-edit` values.

---

## PHASE P5 — MEASURED MODEL PROFILES

Goal:
Replace curated guesses with evidence.

Create a reproducible measurement pipeline using:

- AgentRouter Gold;
- LLMRouterBench where mapping is valid;
- coding tasks;
- reasoning tasks;
- summarization;
- long context;
- tool use;
- instruction following;
- multilingual tasks;
- safety;
- real user feedback.

Each score must contain:

- source;
- version;
- date;
- sample size;
- confidence;
- methodology;
- model snapshot;
- cost;
- latency;
- failure rate.

Never automatically overwrite production profiles.

Generate a proposal:

agentrouter eval propose-model-profiles

Require review before activation:

agentrouter models apply-profile-proposal <file>

Include uncertainty intervals where feasible.

---

## PHASE P6 — FINISH THE 100-POINT EVALUATION SYSTEM

Complete all scoring dimensions:

- classification: 30
- routing: 25
- safety/security: 15
- CLI/platform: 10
- provider/registry: 8
- feedback/storage: 7
- performance/stability: 5

Finish:

- routing evaluator;
- safety evaluator;
- platform evaluator;
- provider evaluator;
- feedback evaluator;
- performance evaluator.

Complete the testing stack:

- pytest;
- branch coverage;
- Ruff;
- GitHub Actions;
- Hypothesis;
- Promptfoo;
- mutmut;
- Bandit;
- pip-audit;
- secret scanning;
- pytest-benchmark;
- DVC;
- MLflow.

Never rescale a partial score to look complete.

---

## PHASE P7 — PRODUCTION API AND SDK

Create a local production-ready service surface.

Preferred architecture:

agentrouter/server/
app.py
routes/
schemas/
auth/
policy/
services/
middleware/
telemetry/

Initial endpoints:

GET /health
GET /ready
GET /v1/models
GET /v1/hosts
POST /v1/classify
POST /v1/route
GET /v1/decisions/{id}
POST /v1/feedback
POST /v1/execute/dry-run

Actual remote execution must remain disabled by default.

Build:

- OpenAPI schema;
- Python SDK;
- TypeScript SDK;
- idempotency;
- request IDs;
- structured errors;
- rate limiting design;
- local API-key authentication option;
- audit records;
- versioned API contract.

Use SQLite for local mode.

Design a PostgreSQL path for hosted/team mode without forcing it into local
installations.

---

## PHASE P8 — PLUGIN AND SKILL ECOSYSTEM

This is a major adoption phase.

Inspect the latest official specifications before implementation.

Build an officially structured Claude Code integration:

integrations/claude-code/
plugin or skill manifest
SKILL.md
commands
hooks where justified
installation script
examples
tests
version metadata

Expected workflows:

/route
/route-plan
/route-subtasks
/route-explain
/route-execute
/route-review

Build a host-agnostic integration:

integrations/generic/AGENTS.md

Build a Codex integration:

integrations/codex/

Consider an MCP server only where it provides real interoperability:

- list models;
- list hosts;
- classify;
- route;
- explain;
- record feedback.

Do not make MCP responsible for unsafe direct execution by default.

Create:

agentrouter plugin list
agentrouter plugin install claude-code
agentrouter plugin install codex
agentrouter plugin doctor
agentrouter plugin uninstall <name>

Installation must be:

- one command;
- reversible;
- idempotent;
- platform-aware;
- tested on Windows and Linux;
- safe for existing user configuration;
- able to show the exact files it will modify.

Do not overwrite user configuration without a backup and confirmation.

---

## PHASE P9 — CLI AND USER EXPERIENCE

Make the product pleasant enough for everyday use.

Create an onboarding wizard:

agentrouter setup

It should:

- explain local privacy;
- initialize a home directory;
- discover hosts;
- detect credentials without exposing them;
- select cost/quality preference;
- configure stable/preview policy;
- run a first sample route;
- show how to install plugins.

Improve output:

- exact model;
- vendor;
- host;
- availability;
- quality confidence;
- cost estimate;
- latency estimate;
- context;
- risk;
- safety gate;
- fallback;
- command preview;
- why this choice;
- why alternatives lost.

Add:

- concise default mode;
- `--details`;
- `--json`;
- `--quiet`;
- accessible no-color mode;
- shell completion;
- actionable errors;
- progress indicators only where useful.

Add a local interactive dashboard or TUI only after the CLI is strong.

---

## PHASE P10 — OBSERVABILITY, SECURITY AND GOVERNANCE

Implement:

- structured logs;
- audit events;
- request/decision correlation IDs;
- optional OpenTelemetry;
- error categorization;
- catalog freshness metrics;
- routing latency;
- recommendation distribution;
- fallback frequency;
- user override rate;
- safety-block rate;
- provider failure rate;
- estimated versus actual cost where available.

Security:

- threat model;
- dependency scanning;
- secret scanning;
- shell-injection regression suite;
- malicious registry fixtures;
- tampered catalog detection;
- signed/checksummed snapshots where practical;
- safe plugin installation;
- least privilege;
- explicit destructive-action policy.

Privacy:

- local-first default;
- no telemetry by default;
- explicit opt-in;
- redact task text when configured;
- retention controls;
- deletion/export commands.

---

## PHASE P11 — TEAM AND HOSTED ARCHITECTURE

Design, document and implement the smallest production-capable hosted path.

Separate:

CONTROL PLANE

- organizations;
- users;
- policies;
- shared model registry;
- billing metadata;
- benchmark profiles;
- audit;
- admin.

DATA PLANE

- task classification;
- routing;
- host resolution;
- execution gateway;
- provider calls.

Local mode must remain fully supported.

Hosted mode should add:

- PostgreSQL;
- migrations;
- tenant isolation;
- authentication;
- RBAC;
- rate limits;
- usage metering;
- policy enforcement;
- encrypted secrets;
- background work only where necessary.

Do not deploy or provision paid infrastructure without explicit permission.

Provide:

- Dockerfile;
- docker-compose development stack;
- production deployment guide;
- environment reference;
- backup/restore guide;
- upgrade guide.

---

## PHASE P12 — DISTRIBUTION AND ADOPTION

A technically strong project does not become popular automatically.

Create:

- a polished README;
- a 60-second quick start;
- demo GIF/video script;
- architecture diagram;
- model-routing examples;
- comparison against manual model choice;
- clear privacy page;
- FAQ;
- troubleshooting guide;
- plugin installation guide;
- API documentation;
- SDK examples;
- benchmark methodology;
- honest limitations;
- contribution guide;
- roadmap;
- release notes.

Packaging:

- PyPI-ready package;
- reproducible wheel and sdist;
- version command;
- installation validation;
- semantic versioning;
- changelog automation;
- signed release recommendations;
- GitHub release workflow;
- package provenance/SBOM where practical.

Create example templates:

examples/
coding-agent-routing/
rag-routing/
low-cost-batch-routing/
high-risk-production-change/
local-private-routing/
team-policy-routing/
api-integration/
claude-code-plugin/
codex-integration/

Create extension documentation:

- adding a vendor;
- adding a model source;
- adding an execution host;
- adding an evaluator;
- adding a plugin;
- adding a policy.

---

## PHASE P13 — PUBLIC BETA RELEASE GATES

Public beta is allowed only when:

Core:

- no production placeholder model IDs;
- exact model and host are shown;
- offline route works;
- catalog refresh failure is atomic;
- high-risk execution is blocked;
- no shell injection;
- old databases migrate;
- old decisions remain explainable;
- package installs from the wheel;
- Windows and Linux pass.

Evaluation:

- full 100-point evaluator is implemented;
- overall grade >= 85;
- task-type macro F1 >= 0.90;
- high-risk recall = 1.00;
- approval accuracy = 1.00;
- tool-needs F1 >= 0.90;
- synthetic routing top-1 >= 0.95;
- safety failures = 0.

Product:

- one-command setup;
- one-command Claude Code integration;
- one-command Codex integration;
- understandable README;
- real examples;
- clear limitations;
- no hidden telemetry;
- reversible plugin installation.

Security:

- Bandit passes or findings are justified;
- pip-audit passes or findings are documented;
- secret scan passes;
- injection suite passes;
- dependency lock strategy is documented;
- threat model exists.

Performance:

- classification and routing meet documented targets;
- no severe memory regression;
- large registries remain usable;
- CLI startup is practical.

Do not label the release production-ready merely because beta gates pass.

---

## PHASE P14 — PRODUCTION RELEASE GATES

Production release additionally requires:

- real user beta feedback;
- private reviewed holdout;
- operational runbook;
- incident-response procedure;
- rollback procedure;
- backup/restore verification;
- hosted-mode tenant isolation tests where hosted mode exists;
- catalog update policy;
- deprecation policy;
- privacy and retention controls;
- model-access failure behavior;
- cost-control enforcement;
- documented support matrix;
- migration guide;
- release artifact verification;
- no critical open security issue.

# ====================================================================== 6. SUBAGENT STRATEGY

Use subagents only where independent work or review adds value.

Recommended roles:

1. product-architect
   - maintains product boundaries and architecture decisions.

2. model-catalog-engineer
   - implements vendor catalogs and provenance.

3. routing-evaluation-engineer
   - builds measured profiles and scoring validation.

4. integration-engineer
   - builds Claude Code, Codex and MCP/plugin surfaces.

5. security-reviewer
   - reviews execution, plugin installation, secrets and policies.

6. test-reviewer
   - independently verifies acceptance criteria.

7. documentation-product-reviewer
   - tests onboarding and documentation as a new user.

Do not have multiple agents edit the same files simultaneously.

Use isolated worktrees or clearly separated file ownership where supported.

The builder must not be the only reviewer of its work.

# ====================================================================== 7. PRIORITIZATION

Use this priority formula:

Priority =
user value
× trust improvement
× platform leverage
× adoption leverage
÷ implementation risk

Highest immediate priority:

1. verify the current exact-model routing foundation;
2. finish dynamic catalogs;
3. finish host verification;
4. finish route controls and confidence;
5. replace curated scores with measured evidence;
6. finish the 100-point evaluator;
7. produce a polished installable Claude Code integration;
8. produce a Codex integration;
9. build the API/SDK;
10. prepare public beta distribution.

Do not spend early loops on decorative dashboards while trust-critical routing,
catalog and evaluation work remains unfinished.

# ====================================================================== 8. DEFINITION OF “DONE”

A feature is done only when:

- implementation exists;
- unit tests exist;
- integration or CLI verification exists;
- negative paths are tested;
- backward compatibility is considered;
- security impact is considered;
- documentation exists;
- acceptance evidence is recorded;
- no false completion claim is made.

“Adapter exists” does not mean “full dataset tested.”

“Environment variable exists” does not mean “host access verified.”

“Real model name” does not mean “ranking is benchmark-proven.”

“Tests pass locally” does not mean “cross-platform CI is green.”

“Plugin files exist” does not mean “installation is safe and usable.”

# ====================================================================== 9. FINAL REPORT AFTER EACH MAJOR PHASE

Report:

1. objective completed;
2. files changed;
3. architecture decision;
4. tests added;
5. commands run;
6. exact results;
7. coverage impact;
8. backward compatibility;
9. security implications;
10. remaining failures;
11. external blockers;
12. next automatic loop objective.

Do not ask whether to continue.

Continue automatically unless a named terminal state is reached.

# ====================================================================== 10. FINAL PROGRAM COMPLETION REPORT

When all locally actionable acceptance criteria are complete, return:

1. Executive product status.
2. Completed phases.
3. Current architecture.
4. CLI surfaces.
5. API and SDK surfaces.
6. Plugin and skill surfaces.
7. Dataset and evaluation status.
8. Model-catalog status.
9. Host support matrix.
10. Security status.
11. Test counts.
12. Line and branch coverage.
13. Mutation score.
14. Performance benchmarks.
15. Windows/Linux/Python support.
16. Package-build status.
17. Public-beta readiness.
18. Production-readiness gaps.
19. External blockers.
20. Exact manual commands for the owner.
21. Git review commands.
22. Suggested commit breakdown.
23. Suggested release version.
24. A continuation roadmap for the next release.

Never commit or push.

# ====================================================================== 11. START NOW

Begin by:

1. reading all required project files;
2. creating the loop memory files;
3. inspecting the current implementation against the latest Assignment A and
   Assignment B reports;
4. running the current baseline;
5. identifying false/stale claims;
6. selecting the first highest-leverage unfinished vertical slice;
7. implementing it;
8. verifying it;
9. recording the loop;
10. continuing automatically.

Do not merely rewrite command.md.

Do not respond with a plan and stop.

Execute the loop until COMPLETE, BLOCKED_EXTERNAL, BLOCKED_USER, UNSAFE,
ENVIRONMENT_FAILURE or CONTEXT_HANDOFF.

======================================================================
FINAL CONTINUOUS AUDIT, REPAIR AND SELF-CORRECTION LOOP
======================================================================

After completing every planned phase, do not stop.

Run a full independent audit of the entire AgentRouter OS product.

The audit must verify the actual implementation against:

- PRODUCT_MASTER_PLAN.md
- PRODUCT_ACCEPTANCE.md
- RELEASE_READINESS.md
- EVALUATION_ACCEPTANCE.md
- SECURITY.md
- TESTING.md
- ARCHITECTURE.md
- CLI_SPEC.md
- API documentation
- plugin installation documentation
- current source code
- current tests
- current generated reports
- current CI configuration

Do not trust previous completion claims.

Treat every existing status, checkbox and report as unverified until supported by
current code, tests and command output.

---

## AUDIT LOOP

Repeat the following loop until all locally actionable issues are fixed.

1. INVENTORY

Inspect the entire repository and list:

- implemented features;
- partially implemented features;
- placeholder implementations;
- dead code;
- duplicated code;
- stale documentation;
- missing tests;
- skipped tests;
- fixture-only integrations;
- external blockers;
- security-sensitive code;
- missing migrations;
- unsupported platforms;
- broken commands;
- misleading completion claims.

2. REQUIREMENT TRACEABILITY

For every requirement in the master plan, create a traceability table:

Requirement
Implementation file
Test file
Verification command
Current status
Evidence
Remaining gap

A requirement may be marked complete only when:

- implementation exists;
- meaningful tests exist;
- the user-facing workflow works;
- negative paths work;
- documentation is accurate;
- current verification passes.

3. BUILD AND INSTALL AUDIT

Verify the product as a real user would:

- build wheel and source distribution;
- install the wheel in a clean virtual environment;
- initialize a fresh AgentRouter home;
- run every public CLI command;
- run setup/onboarding;
- run model catalog commands;
- run host discovery;
- run routing;
- run explanation;
- run dry execution;
- run evaluation;
- install and uninstall each plugin;
- run API and SDK smoke tests.

Editable-install success is not sufficient.

4. FUNCTIONAL AUDIT

Test complete workflows, not isolated functions.

Required workflows include:

- classify task;
- select exact model;
- select exact execution host;
- explain why the model won;
- show fallback;
- calculate cost and latency estimates;
- reject unavailable models;
- handle stale model catalogs;
- handle ambiguous tasks;
- enforce user policies;
- log decisions;
- accept feedback;
- adapt safely;
- preserve old decisions;
- migrate old databases;
- run offline;
- recover from provider failures.

5. MODEL-CATALOG AUDIT

Verify:

- exact model IDs;
- official source;
- retrieval date;
- release channel;
- context limits;
- output limits;
- pricing;
- supported modalities;
- tool support;
- deprecation status;
- metadata provenance;
- stale-record detection;
- atomic refresh;
- rollback after failed refresh.

Never accept guessed metadata as official.

Never accept curated ability scores as benchmark-measured scores.

6. ROUTING-QUALITY AUDIT

Run:

- AgentRouter Gold;
- public benchmark samples;
- synthetic routing cases;
- long-context cases;
- multilingual cases;
- tool-use cases;
- cost-sensitive cases;
- high-quality preference cases;
- ambiguous prompts;
- adversarial prompts.

Compare AgentRouter against:

- random routing;
- cheapest-model routing;
- strongest-model routing;
- best-single-model routing;
- oracle routing where benchmark data permits.

Measure:

- quality;
- cost;
- latency;
- quality per dollar;
- top-1 success;
- top-2 success;
- oracle regret;
- unnecessary frontier usage;
- under-routing rate;
- fallback success.

7. SAFETY AND SECURITY AUDIT

Test:

- high-risk auto-execution blocking;
- shell injection;
- command argument injection;
- prompt injection;
- path traversal;
- malicious registry files;
- malformed YAML;
- malicious plugin manifests;
- secret leakage;
- unsafe logging;
- unsafe API errors;
- policy bypass;
- route override bypass;
- stale decision execution;
- host availability changing after routing;
- dependency vulnerabilities;
- accidentally committed secrets.

Use:

- Bandit;
- pip-audit;
- secret scanning;
- mutation testing;
- property-based tests;
- adversarial fixtures.

Any critical safety failure blocks release regardless of total grade.

8. PLATFORM AUDIT

Verify:

- Windows;
- Linux;
- supported Python versions;
- clean virtual environments;
- paths containing spaces;
- Unicode paths;
- PowerShell;
- Bash;
- packaged wheel;
- offline mode;
- fresh installation;
- upgrade from an older AgentRouter version.

Do not mark a platform supported without running it in CI or a verified local
environment.

9. PLUGIN AND SKILL AUDIT

For every integration:

- install from a clean environment;
- verify exact files created;
- verify existing user files are preserved;
- verify backups;
- verify idempotent reinstall;
- verify upgrade;
- verify uninstall;
- verify rollback;
- verify command discovery;
- verify documentation;
- verify Windows and Linux behavior.

A plugin is not complete merely because its manifest exists.

10. API AND SDK AUDIT

Verify:

- OpenAPI schema;
- request validation;
- structured errors;
- authentication;
- idempotency;
- timeouts;
- rate-limit behavior;
- backward compatibility;
- Python SDK;
- TypeScript SDK;
- generated examples;
- version negotiation;
- local API mode;
- no remote execution by default.

11. PERFORMANCE AUDIT

Measure:

- CLI startup;
- classification latency;
- routing latency;
- catalog loading;
- routing across large model pools;
- evaluation throughput;
- SQLite performance;
- API latency;
- memory usage;
- plugin installation time.

Compare with stored baselines.

Investigate meaningful regressions.

12. DOCUMENTATION AUDIT

Verify every documented command against the current package.

Remove or correct:

- stale commands;
- fake screenshots;
- incorrect test counts;
- unsupported model claims;
- fixture-only claims presented as real evaluations;
- outdated architecture;
- incomplete installation steps;
- inaccurate release status.

Documentation must match real behavior.

13. INDEPENDENT REVIEW

Use independent reviewer subagents where available.

Separate roles:

- architecture reviewer;
- security reviewer;
- testing reviewer;
- user-experience reviewer;
- documentation reviewer;
- release-readiness reviewer.

The agent that implemented a feature must not be the only agent that verifies
it.

Reviewers must return:

- critical issues;
- major issues;
- minor issues;
- missing evidence;
- false claims;
- recommended fixes.

14. ROOT-CAUSE REPAIR

For every discovered issue:

- determine the root cause;
- do not patch only the visible symptom;
- implement the smallest correct repair;
- add a regression test;
- rerun the affected workflow;
- rerun broader tests when shared code changes;
- update documentation;
- update audit evidence.

Do not weaken tests.

Do not remove difficult benchmark cases.

Do not lower release thresholds merely to obtain a pass.

15. REGRESSION LOOP

After every repair:

- run focused tests;
- run full tests;
- run coverage;
- run security checks;
- run package smoke;
- rerun affected benchmarks;
- compare before and after;
- inspect new failures;
- continue fixing.

16. RELEASE-GATE AUDIT

Recalculate release readiness from current evidence.

Public beta requires:

- all local acceptance items complete;
- overall evaluation grade >= 85;
- task-type macro F1 >= 0.90;
- high-risk recall = 1.00;
- approval accuracy = 1.00;
- tool-needs F1 >= 0.90;
- synthetic routing top-1 >= 0.95;
- zero critical safety failures;
- Windows and Linux green;
- wheel install verified;
- plugin install/uninstall verified;
- no production placeholder model;
- no false documentation claims.

Production release additionally requires:

- real user beta feedback;
- private unseen holdout;
- operational runbook;
- rollback verification;
- backup/restore verification;
- incident-response process;
- privacy controls;
- model-catalog maintenance policy;
- no unresolved critical or high-severity security issue.

---

## SELF-DECISION RULES

Make implementation decisions independently when:

- the choice is reversible;
- it does not spend money;
- it does not require secrets;
- it does not change production infrastructure;
- it preserves backward compatibility;
- it follows existing architecture and product goals;
- it can be verified locally.

Do not ask the user routine development questions.

Choose sensible defaults and document them.

Ask the user only when:

- payment or paid inference is required;
- credentials are required;
- infrastructure may be deployed or modified;
- data may be deleted;
- a breaking API decision is unavoidable;
- a licensing or legal choice is required;
- marketplace publication requires owner action;
- a product decision has multiple incompatible long-term directions.

---

## AUDIT OUTPUT

Maintain:

AUDIT_STATE.json
AUDIT_REPORT.md
AUDIT_FINDINGS.csv
AUDIT_TRACEABILITY.md
AUDIT_REPAIRS.md
RELEASE_READINESS.md

Each finding must include:

- id;
- severity;
- area;
- requirement;
- evidence;
- root cause;
- repair;
- test added;
- verification command;
- result;
- status.

Severity levels:

- critical;
- high;
- medium;
- low;
- informational.

---

## STOP CONDITIONS

Continue the audit-and-repair loop automatically until one of these states is
reached:

AUDIT_COMPLETE

- all locally actionable findings resolved;
- all release gates recalculated;
- no unsupported completion claim remains;
- final reports generated.

BLOCKED_EXTERNAL

- only credentials, paid APIs, Docker-heavy external benchmarks, marketplace
  approval, legal review or user infrastructure remain.

BLOCKED_USER

- an irreversible or major product decision requires the owner.

UNSAFE

- continuing would risk destructive or insecure changes.

ENVIRONMENT_FAILURE

- the local environment cannot proceed after diagnosis and reasonable fallback
  attempts.

CONTEXT_HANDOFF

- session resources are nearly exhausted;
- write exact resumable state and the next command;
- do not claim completion.

Do not stop because one test run is green.

Do not stop because the implementation matches the original plan.

Stop only after independently auditing the complete product, fixing every
locally actionable issue and producing evidence for the remaining status.

Do not commit or push.
