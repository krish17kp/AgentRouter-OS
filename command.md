Read CLAUDE.md, EVALUATION_STATUS.md, EVALUATION_ACCEPTANCE.md and
EVALUATION_HANDOFF.md first.

Do not run git add, commit, push or create a PR.

Complete the real external dataset preparation for AgentRouter OS.

Current issue:
CLINC150, BANKING77 and MASSIVE show "needs datasets", while the other
external adapters are still fixture-only or SKIPPED_EXTERNAL.

Tasks:

1. Activate the existing virtual environment.
2. Install the evaluation dependencies using:
   python -m pip install -e ".[eval]"

3. Use this cache root:
   D:\Krish\Agentrouteros\data\huggingface

   Set HF_HOME for the current process and ensure data/ is gitignored.

4. Inspect every dataset adapter before downloading anything.

5. For CLINC150, BANKING77 and MASSIVE:
   - identify the official Hugging Face dataset repository;
   - pin a revision, tag or commit where possible;
   - implement or repair the full prepare/load path;
   - download using the datasets library;
   - normalize records into EvaluationCase;
   - preserve source ids, split, language and intent;
   - report source, revision, license, cache path and record counts;
   - never commit raw dataset files;
   - keep fixture mode for offline CI;
   - make real mode explicit and distinguish it from fixture mode.

6. For LongBench v2:
   - identify the official source;
   - implement the real static dataset loader;
   - preserve context length and task category;
   - run a small real sample;
   - do not mark full success if only a fixture was run.

7. For SWE-bench:
   - download/prepare dataset metadata only;
   - do not run Docker issue-solving workloads yet;
   - clearly separate dataset preparation from dynamic execution.

8. For LLMRouterBench:
   - download or clone the official benchmark source;
   - implement real record loading;
   - do not calculate exact-model routing quality until model_mapping.yaml is
     valid;
   - run schema and normalization tests;
   - report mapping as the remaining blocker if applicable.

9. For TwinRouterBench:
   - prepare the static track;
   - do not run the dynamic Docker/model track;
   - report dynamic execution as SKIPPED_EXTERNAL.

10. Add or finish CLI commands for:
    agentrouter eval prepare --dataset <name>
    agentrouter eval prepare --all
    agentrouter eval status
    agentrouter eval run --dataset <name> --source real
    agentrouter eval run --dataset <name> --source fixture

11. A real run must never silently fall back to fixtures.
    If real data is unavailable, exit clearly with SKIPPED_EXTERNAL or an error.

12. Add tests using mocks and tiny fixtures. Normal CI must remain offline.

13. Run:
    ruff check .
    ruff format --check .
    pytest -q

14. Run real smoke samples for every downloadable dataset and report:
    - dataset
    - source
    - revision
    - license
    - cache path
    - downloaded record count
    - evaluated sample count
    - real / fixture / skipped status
    - exact blocker

Do not claim full integration merely because the Python adapter imports.

Do not commit or push.
# AGENTROUTER OS — REAL MODEL CATALOG, HOST-AWARE ROUTING
# AND EXACT MODEL EXECUTION

This is an implementation assignment. Do not stop at planning.

Repository:
D:\Krish\Agentrouteros
https://github.com/krish17kp/AgentRouter-OS

CURRENT PROBLEM

AgentRouter now classifies these tasks more reasonably:

1. "build a rag system which identifies the pdf very well"
   -> coding / medium / file-edit + shell

2. "for building a fastapi for collecting or scrapping data from the website,
   i need to make a automation for it"
   -> coding / medium / file-edit + shell

However, the recommendations remain unsuitable for a real product:

- cursor/ide-coding-model
- claude-code/fast-coding-model
- claude-code/frontier-coding-model
- openrouter/mid-tier-coding-model

Those are illustrative placeholders, not models that a user can actually
select or execute.

The terminal must recommend exact current models such as:

- Claude Fable 5
- Claude Opus 4.8
- Claude Sonnet 5
- Claude Haiku 4.5
- GPT-5.6 Sol
- GPT-5.6 Terra
- GPT-5.6 Luna
- exact Gemini models returned by Google's catalog
- exact OpenRouter model IDs

The router must then select a usable execution host such as:

- Claude Code
- Codex CLI
- OpenRouter API
- Anthropic API
- OpenAI API
- Google Gemini API
- another verified supported host

Cursor is an execution environment/IDE, not a model vendor.
Claude Code is an execution host, not a model vendor.
Codex CLI is an execution host, not a model vendor.

NON-NEGOTIABLE RULES

1. Read before editing:
   - CLAUDE.md
   - README.md
   - ARCHITECTURE.md
   - MODEL_REGISTRY_SCHEMA.md
   - ROUTING_RULES.md
   - PROVIDER_ADAPTER_SPEC.md
   - CLI_SPEC.md
   - TESTING.md
   - EVALUATION_STATUS.md
   - EVALUATION_ACCEPTANCE.md
   - EVALUATION_HANDOFF.md
   - pyproject.toml
   - agentrouter/seeds/models.yaml
   - agentrouter/seeds/providers.yaml
   - agentrouter/schema.py
   - agentrouter/engine.py
   - agentrouter/registry.py
   - agentrouter/refresh.py
   - agentrouter/cli.py
   - all execution and evaluation modules
   - all tests
   - all GitHub Actions workflows

2. Git restrictions:
   - Do not run git add.
   - Do not commit.
   - Do not push.
   - Do not create a pull request.
   - Do not tag.
   - I will review and perform all Git operations manually.

3. Do not claim CI is green while any job is failing.

4. First inspect and repair the current Linux CI failures.
   The latest push showed failures on Python 3.10, 3.11, 3.12, and 3.13.
   Windows and build-smoke alone do not prove the suite is green.

5. Run normal tests without API keys or network access.

6. Never invent model availability, pricing, capability, benchmarks, or API IDs.

7. Every model field must carry provenance:
   - official_api
   - official_docs_snapshot
   - benchmark_measured
   - manually_curated
   - heuristic

8. Dynamic generated model files must remain separate from manually curated
   entries. Manual entries may override generated metadata intentionally.

9. Preserve backward compatibility for existing databases and JSON output.

10. High-risk tasks must remain blocked from automatic execution.

======================================================================
PHASE 1 — FIX THE MODEL DOMAIN DESIGN
======================================================================

The present schema conflates provider/vendor and execution host.

Replace that design with two separate entities.

A. Model vendor/provider

Examples:
- anthropic
- openai
- google
- mistral
- xai
- deepseek
- meta
- qwen

B. Execution host

Examples:
- claude-code
- codex-cli
- anthropic-api
- openai-api
- gemini-api
- openrouter
- cursor-manual
- local-cli
- manual

A model must use a stable key:

vendor/model_id

Examples:

anthropic/claude-sonnet-5
anthropic/claude-opus-4-8
anthropic/claude-fable-5
openai/gpt-5.6-terra
openai/gpt-5.6-sol
google/gemini-3.5-flash

Create backward-compatible schemas resembling:

class ModelEntry:
    vendor: str
    model_id: str
    display_name: str

    family: str | None
    release_channel: stable | preview | experimental | deprecated
    snapshot_type: pinned | alias | unknown

    context_window: int
    max_input_tokens: int | None
    max_output_tokens: int

    input_price_per_million: float | None
    output_price_per_million: float | None
    pricing_currency: str
    pricing_basis: api_list | subscription | openrouter | unknown
    pricing_effective_date: date | None

    latency_tier: fast | medium | slow
    ability: Ability
    ability_source: official | benchmark | curated | heuristic
    ability_confidence: float | None

    tool_support: list[str]
    vision_support: bool
    audio_support: bool
    video_support: bool
    reasoning_support: bool

    ideal_use_cases: list[str]
    avoid_use_cases: list[str]
    deprecation_status: active | deprecated | retired

    execution_targets: list[ExecutionTarget]

    source: str
    source_url_or_identifier: str | None
    last_verified: date | None

class ExecutionTarget:
    host: str
    host_model_id: str
    execution_mode: cli | api | manual
    command_template: list[str] | None
    required_command: str | None
    required_env: list[str]
    supports_noninteractive: bool
    supports_file_edit: bool
    supports_shell: bool
    availability: available | unavailable | unknown
    availability_reason: str | None

If changing the existing field names would cause excessive breakage, implement
a migration/compatibility layer:

- accept legacy `provider`;
- map it to `vendor`;
- never produce new placeholder entries;
- preserve old saved decisions for explain/replay.

ModelEntry.key must become:

vendor/model_id

The ranking engine selects a MODEL.

A separate host-resolution stage selects HOW that model will run.

Do not combine model capability and host availability into one opaque score.

======================================================================
PHASE 2 — REPLACE PLACEHOLDER SEED MODELS
======================================================================

Remove these from the default user-facing registry:

- frontier-coding-model
- fast-coding-model
- frontier-reasoning-model
- general-purpose-model
- legacy-general-model
- strong-coding-model
- mid-tier-coding-model
- cheap-fast-model
- long-context-writer-model
- ide-coding-model

They may remain only inside synthetic routing tests where obviously named as
test fixtures.

Create a dated bundled offline snapshot containing real models.

At minimum include current official Anthropic entries:

1. Claude Fable 5
   vendor: anthropic
   model_id: claude-fable-5
   display_name: Claude Fable 5
   family: fable
   context_window: 1000000
   max_output_tokens: 128000

2. Claude Opus 4.8
   vendor: anthropic
   model_id: claude-opus-4-8
   display_name: Claude Opus 4.8
   family: opus
   context_window: 1000000
   max_output_tokens: 128000

3. Claude Sonnet 5
   vendor: anthropic
   model_id: claude-sonnet-5
   display_name: Claude Sonnet 5
   family: sonnet
   context_window: 1000000
   max_output_tokens: 128000

4. Claude Haiku 4.5
   vendor: anthropic
   model_id: claude-haiku-4-5-20251001
   alias: claude-haiku-4-5
   display_name: Claude Haiku 4.5
   family: haiku
   context_window: 200000
   max_output_tokens: 64000

At minimum include current official OpenAI entries:

1. GPT-5.6 Sol
   vendor: openai
   model_id: gpt-5.6-sol
   alias: gpt-5.6
   display_name: GPT-5.6 Sol
   context_window: 1050000
   max_output_tokens: 128000

2. GPT-5.6 Terra
   vendor: openai
   model_id: gpt-5.6-terra
   display_name: GPT-5.6 Terra
   context_window: 1050000
   max_output_tokens: 128000

3. GPT-5.6 Luna
   vendor: openai
   model_id: gpt-5.6-luna
   display_name: GPT-5.6 Luna
   context_window: 1050000
   max_output_tokens: 128000

For Google:

- inspect the official Gemini Models API;
- include current stable model IDs returned by the official API;
- mark preview models as preview;
- do not silently rank experimental models for production usage;
- do not guess model IDs from marketing names.

Do not blindly assign ability scores based only on price.

For bundled models:

- use conservative curated scores;
- mark ability_source=curated;
- document why;
- record last_verified;
- assign low or medium confidence until benchmark measurements exist.

Create a test that fails if any default production seed contains:

- frontier-coding-model
- fast-coding-model
- general-purpose-model
- ide-coding-model
- cheap-fast-model

======================================================================
PHASE 3 — DYNAMIC MODEL CATALOGS
======================================================================

Implement first-class refresh adapters.

Commands:

agentrouter models refresh anthropic
agentrouter models refresh openai
agentrouter models refresh google
agentrouter models refresh openrouter
agentrouter models refresh --all
agentrouter models list
agentrouter models list --available
agentrouter models show anthropic/claude-sonnet-5

Keep `agentrouter providers refresh` as a deprecated compatibility alias if
needed.

Anthropic refresh:

- use Anthropic's official Models API when authentication exists;
- retrieve exact model IDs and token/capability limits;
- never print API keys;
- support fixture/mocked tests;
- fall back to the bundled snapshot offline.

OpenAI refresh:

- use the official model-list endpoint;
- preserve exact IDs visible to the user's account;
- join official/maintained capability metadata separately;
- do not assume that the model-list endpoint supplies pricing and benchmarks.

Google refresh:

- use the official Gemini Models API;
- preserve stable/preview/experimental status;
- preserve exact supported methods and limits.

OpenRouter refresh:

- use `/api/v1/models`;
- preserve:
  - exact id;
  - canonical slug;
  - display name;
  - context length;
  - pricing;
  - supported parameters;
  - architecture/modalities;
  - provider metadata;
  - latency/throughput data when available;
- support filtering by tools, modality, vendor, price and context;
- do not convert every OpenRouter model into the same generic capability score.

Generated registry files:

models.anthropic.generated.yaml
models.openai.generated.yaml
models.google.generated.yaml
models.openrouter.generated.yaml

Manual overrides continue to win.

Add stale-catalog warnings.

Suggested policy:

- informational warning after 30 days;
- prominent warning after 90 days;
- never delete models automatically;
- respect explicit deprecation status.

======================================================================
PHASE 4 — HOST DISCOVERY AND AVAILABILITY
======================================================================

Create:

agentrouter hosts list
agentrouter hosts doctor
agentrouter hosts refresh
agentrouter hosts show claude-code

Detect locally:

- `claude`
- `codex`
- other explicitly supported CLIs

Use `shutil.which`, safe read-only version/auth checks, and timeouts.

Claude Code:

- detect whether `claude` exists;
- run safe version/auth diagnostics;
- support exact model IDs and aliases:
  - fable
  - opus
  - sonnet
  - haiku
- support command construction with:
  `claude -p --model <model-id> --effort <level> <prompt>`
- support fallback model chains;
- never use `--dangerously-skip-permissions`.

Codex CLI:

- detect whether `codex` exists;
- use its catalog/debug command where available;
- support:
  `codex exec --model <model-id> <prompt>`
- use safe sandbox/approval defaults;
- never use danger-full-access or yolo options automatically.

OpenRouter/API hosts:

- mark available only if the required environment variable exists;
- never print its value;
- use a connectivity check only when explicitly requested;
- normal routing must work offline.

Cursor:

- do not pretend Cursor is an exact model.
- treat Cursor as a manual execution host unless a documented, tested,
  noninteractive exact-model CLI interface exists.
- output instructions instead of fake automatic execution.

Availability states:

available
unavailable
unknown

Do not convert unknown to available.

Default routing should prefer models that have at least one available host.

Add:

--include-unavailable

to allow global comparison across models the user cannot currently run.

======================================================================
PHASE 5 — TWO-STAGE ROUTING
======================================================================

Implement two distinct stages.

Stage 1: Model selection

Input:
- task classification;
- context;
- tools;
- risk;
- cost policy;
- latency policy;
- quality profiles.

Output:
- exact vendor/model ID;
- fallback exact vendor/model ID.

Stage 2: Execution-route selection

Input:
- selected model;
- available hosts;
- user preference;
- account availability;
- API/subscription cost basis;
- privacy requirements.

Output:
- selected execution host;
- host model ID;
- exact safe command/API adapter.

Do not award capability points because a model is available locally.

Do not award model-quality points because the host is preferred.

When the highest-scoring model is unavailable:

- show it as the global best only when requested;
- choose the best available model as the actionable recommendation;
- explain the distinction.

Example:

Global best:
Claude Fable 5 — unavailable on current account

Best available:
Claude Sonnet 5 via Claude Code

======================================================================
PHASE 6 — DETAILED TERMINAL OUTPUT
======================================================================

Change the normal output from:

1 claude-code/fast-coding-model

to a detailed but readable format.

Required default output:

Recommendation

  Model:          Claude Sonnet 5
  Vendor:         Anthropic
  Model ID:       claude-sonnet-5
  Run through:    Claude Code
  Host model ID:  claude-sonnet-5
  Availability:   available
  Release:        stable
  Context:        1,000,000 tokens
  Max output:     128,000 tokens
  Effort:         high
  Pricing basis:  Anthropic API list price / subscription / unknown
  Score:          0.91

Fallback

  Model:          GPT-5.6 Terra
  Vendor:         OpenAI
  Model ID:       gpt-5.6-terra
  Run through:    Codex CLI
  Availability:   available
  Score:          0.88

Why this model:
- suitable for coding;
- required tools are supported;
- context fits comfortably;
- medium complexity does not justify the most expensive model;
- available through an authenticated local host.

Execution:
  agentrouter execute d_00012 --yes

Command preview:
  claude --model claude-sonnet-5 --effort high -p "<generated prompt>"

The preview must redact the full prompt by default.

Add verbose options:

agentrouter route "<task>" --details
agentrouter route "<task>" --json
agentrouter explain <id>
agentrouter explain <id> --hosts
agentrouter explain <id> --pricing
agentrouter explain <id> --all-models

JSON must include:

recommendation:
  model_key
  vendor
  model_id
  display_name
  release_channel
  score
  terms
  metadata_provenance

execution_route:
  host
  host_model_id
  availability
  execution_mode
  command_preview
  required_env
  unavailable_reason

fallback:
  model details
  execution route

Do not remove existing keys abruptly. Add compatibility keys or version the
JSON contract.

======================================================================
PHASE 7 — DIRECT EXECUTION
======================================================================

Enhance the existing command:

agentrouter execute <decision-id> --yes

It must run the exact model and exact host stored with the decision.

Examples:

Claude Code:
claude -p --model claude-sonnet-5 --effort high "<prompt>"

Codex:
codex exec --model gpt-5.6-terra "<prompt>"

OpenRouter/API:
use the relevant API adapter and exact model ID.

Security:

- use argv arrays;
- never use shell=True;
- never interpolate into a shell command;
- preserve existing high-risk hard block;
- require --yes;
- redact secrets;
- propagate subprocess exit code;
- time out cleanly where appropriate;
- do not execute when availability=unknown;
- do not silently change models;
- if a host performs its own fallback, report that explicitly.

Add optional override commands:

agentrouter execute <id> --host claude-code --model claude-sonnet-5 --yes

Overrides must:

- be validated;
- be logged;
- be shown to the user;
- never bypass safety gates.

Add a dry run:

agentrouter execute <id> --dry-run

======================================================================
PHASE 8 — ROUTING CONTROLS
======================================================================

Add useful route overrides:

--vendor anthropic
--vendor openai
--host claude-code
--host codex-cli
--model anthropic/claude-sonnet-5
--max-price-per-million
--max-estimated-cost
--prefer-fast
--prefer-cheap
--prefer-quality
--available-only
--include-unavailable
--stable-only
--allow-preview
--effort low|medium|high|xhigh|max

Explicit overrides must beat inference.

Invalid combinations must fail clearly.

Examples:

agentrouter route "build a RAG backend" --vendor anthropic

agentrouter route "fix a small typo" --prefer-cheap

agentrouter route "investigate a production outage" \
  --prefer-quality \
  --stable-only

======================================================================
PHASE 9 — MODEL-SPECIFIC SCORING
======================================================================

Do not rank models only by generic family labels.

Support measured or curated profiles for:

- coding;
- reasoning;
- writing;
- analysis;
- summarization;
- tool use;
- agentic reliability;
- long-context;
- vision;
- instruction following;
- speed;
- failure rate.

Every score must identify its source.

Example:

ability_source:
  benchmark: llmrouterbench
  version: 2026-06
  sample_count: 2400
  measured_at: 2026-07-10

Or:

ability_source:
  method: curated
  confidence: low
  reason: no comparable benchmark available

Never imply that curated scores are objective benchmarks.

Build ability-overrides from real evaluation evidence, but never overwrite the
active registry automatically.

======================================================================
PHASE 10 — CLASSIFICATION IMPROVEMENTS OBSERVED
======================================================================

Preserve the corrected behavior for:

"build a rag system which identifies the pdf very well"

Expected:
- coding
- medium or high
- file-edit and shell
- actual exact model recommendation

For:

"for building a fastapi for collecting or scrapping data from the website,
i need to make a automation for it"

Expected:
- coding
- medium
- code output
- file-edit
- shell
- web/network or browser tool requirement where appropriate

Review the tool taxonomy.

Consider explicit tools:

- web-search
- network-http
- browser-automation
- file-read
- file-edit
- shell
- database
- vision
- API access

Do not use only the generic `web` label if greater precision improves routing.

======================================================================
PHASE 11 — TESTING
======================================================================

Before declaring completion, add tests for:

1. Default production seed contains no placeholder model IDs.
2. Exact Claude model names appear in CLI output.
3. Exact OpenAI model names appear in CLI output.
4. Vendor and execution host are distinct.
5. Claude Code command uses exact model ID.
6. Codex command uses exact model ID.
7. Command construction never uses shell=True.
8. Unavailable host is not chosen as actionable recommendation.
9. Unknown availability is not called available.
10. `--include-unavailable` shows global unavailable choices.
11. Stable-only excludes preview and experimental models.
12. Preview models require explicit policy permission.
13. Deprecated and retired models are handled correctly.
14. Manual registry overrides generated entries.
15. Model refresh is deterministic and idempotent.
16. API keys never appear in output or logs.
17. Old saved decisions remain explainable.
18. Old databases migrate safely.
19. JSON remains backward compatible.
20. Exact fallback model and host are shown.
21. High-risk execution remains blocked.
22. Execution overrides cannot bypass safety.
23. Model unavailable between route and execute fails safely.
24. Prices include effective dates and provenance.
25. Stale catalogs produce warnings.
26. Offline mode works without internet.
27. All provider HTTP tests are mocked.
28. Linux Python 3.10–3.13 CI passes.
29. Windows CI passes.
30. Wheel installation and CLI smoke tests pass.

Add snapshot tests for the human-readable output.

Add regression tests for:

- RAG task;
- FastAPI scraping automation task;
- payment-module task;
- sales-guide application task.

======================================================================
PHASE 12 — CI REPAIR AND FINAL VERIFICATION
======================================================================

First reproduce the current Linux CI failure.

Do not guess.

Inspect the failing step and fix the root cause.

Run:

ruff check .
ruff format --check .

pytest -q

pytest \
  --cov=agentrouter \
  --cov-branch \
  --cov-report=term-missing

python -m build

Install the wheel in a clean virtual environment.

Run:

agentrouter --version
agentrouter init
agentrouter models list
agentrouter hosts doctor

agentrouter route \
  "build a rag system which identifies the pdf very well"

agentrouter route \
  "for building a fastapi for collecting or scrapping data from the website, i need to make a automation for it"

agentrouter route \
  "Refactor the payment module and add unit tests"

For every result verify:

- real model name;
- real model ID;
- vendor;
- execution host;
- availability;
- fallback;
- command preview;
- explanation;
- no placeholder models.

Test dry execution:

agentrouter execute <low-risk-id> --dry-run

Do not perform paid API calls.

Do not run actual modifying agents during tests.

Use fake subprocess executors.

======================================================================
FINAL RESPONSE
======================================================================

Return:

1. Current CI root cause.
2. Files changed.
3. Schema migration details.
4. Models added.
5. Providers/catalogs implemented.
6. Hosts implemented.
7. Example output for the RAG task.
8. Example output for the FastAPI scraping task.
9. Exact execution command previews.
10. Test count.
11. Line and branch coverage.
12. Linux CI-equivalent results.
13. Windows results.
14. Packaging result.
15. Remaining limitations.
16. Commands I should run manually.
17. Suggested commit message.

Do not commit or push.