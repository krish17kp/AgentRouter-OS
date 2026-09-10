# §10 Product Audit — AgentRouter OS — 2026-07-19

**Trigger:** 7 local tasks completed (> 5-task threshold) since last audit.
**Scope:** uncommitted working tree on top of HEAD `602321a` (TASK-001..007).
**Method:** four independent read-only reviewers (architecture, security, verification,
customer), each re-deriving from source + runtime probes and a fresh-wheel pip install.
No verdict trusted from checkboxes; every headline claim reproduced.

## Verdict: PASS (after repair)

All four reviewers PASS. The audit surfaced **1 CRITICAL, 6 HIGH, 6 MEDIUM, 4 LOW**;
every locally-actionable finding was fixed this session and the complete audit was
re-run to a clean 4/4 PASS. Remaining open items are external/owner-blocked only.

## Findings and disposition

### CRITICAL — FIXED
- **Eval broken on real pip install.** `benchmarks/` + `evaluation/fixtures/` lived
  outside the package and resolved via `__file__…parents[3]`; not packaged → `eval run`
  / `evaluate` failed with "gold benchmark not found" on any wheel install.
  **Fix:** moved data under `agentrouter/benchmarks/` + `agentrouter/evaluation/fixtures/`,
  resolve via `importlib.resources` (`evaluation/base.py` helpers), added package-data.
  **Verified:** fresh venv, non-repo cwd → `eval run --all` = 98.32/100, 7/7 gates PASS;
  data files confirmed inside the wheel.

### HIGH — FIXED
1. `--prohibit-tool <typo>` silently no-op → now errors with a "did you mean?" hint.
2. `server`/`mcp --help` swallowed `[server]`/`[mcp]` → markup escaped, renders correctly.
3. Em-dash mojibake in printed strings AND `setup`/`execute --help` on cp437/cp1252 →
   replaced with ASCII `-` (verified 0 non-ASCII bytes across all user-facing surfaces).
4. `context_band_accuracy=0.945` measured gold-wording match, not generalization →
   documented as a known limitation (regression guard, not release-grade generalization).
5. TASK-004 `context_tokens` affects default routing (eligibility + score), broader than
   "context-band only" → documented accurately in CHANGELOG.
6. (release) `release.yml` interpolated the release tag into a `run:` shell → env var.

### MEDIUM — FIXED
- `__version__` stale `0.1.0` → sourced from installed metadata (0.4.0).
- `test_cli_smoke` failed under `PYTHONIOENCODING=utf-8` → `encoding="utf-8"` on subprocess.
- `examples/README.md` #5 dead-end → `--max-price` caveat added.
- CHANGELOG omitted server/MCP/plugin/eval/route-control surfaces → added.
- UPGRADING overstated PyPI availability + stale `init --force` text → corrected.
- No uninstall/purge doc → UPGRADING now has an Uninstall section (+ `AGENTROUTER_PLUGIN_ROOT`).

### LOW — FIXED / ACCEPTED
- `GET /v1/<unknown>` returned FastAPI's default shape → handler moved to Starlette's base
  `HTTPException`; now returns the app `{"error":{…}}` envelope. **FIXED.**
- `setup` "no host available" warning was dead code (`manual` always available) → counts
  real hosts only; verified it now fires. **FIXED.**
- `PRODUCT_SCENARIOS.yaml` stale `--max-cost` → `--max-price`. **FIXED.**
- CHANGELOG context-band `Changed` note added. **FIXED.**
- 503 body may echo a local registry path → **ACCEPTED** (local-first; aids debugging).
- `service.py:143` `int()` claimed to 500 → **FALSE POSITIVE** (unreachable; `load_decision`
  guards the id first).

## Also independently confirmed correct (no change)
Constant-time API-key auth + no auth-bypass; no-remote-execution across CLI/REST/MCP;
optional-extra isolation (core import pulls no fastapi/uvicorn/mcp/otel); no import cycles;
bounded rate/idempotency stores; URL-scheme guard; secrets header-only, never logged;
`_execution_route` dedup shape-preserving; bandit 0 issues; ruff/format clean.

## Verification evidence (reproduced)
- `pytest -q` → 426 passed, 1 skipped (env-only: otel installed → no-op-missing test self-skips).
- `ruff check` + `ruff format --check` → clean.
- `bandit -c pyproject.toml -r agentrouter` → 0 issues (5 justified nosec).
- Wheel build → benchmarks + 7 fixtures packaged; fresh-venv `eval run --all` = 98.32, YES.

## Still open — external / owner-blocked (unchanged)
- Mutation score: `mutmut` blocked on Windows+py3.13 (encoding crashes; 3.x Linux-only);
  WSL here has no Linux userland. Linux-CI/WSL follow-up. Documented, not faked.
- P1/P2 (live creds), P5 (paid inference), P11 (owner infra/marketplace), P13/P14
  (real-user beta), P15 (owner product decision).
- Follow-up ticket: `plugin uninstall` leaves an empty `~/.claude/skills/agentrouter/` dir.
- Follow-up: held-out paraphrases for the context-band gold set (generalization).

**Git:** none — fixes staged in the working tree only, not committed or pushed.
