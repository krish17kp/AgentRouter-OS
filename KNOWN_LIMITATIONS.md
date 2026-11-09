# Known Limitations

## Current migration and release limits (2026-11-09)

- Python is still the shipping router. Rust R4 has route, SQLite,
  stored-decision, prompt, and feedback compatibility probes, but no complete
  public Rust CLI/HTTP/MCP replacement. R5–R13 remain open.
- The local and GitHub critical mutation campaigns pass on `3281c41`
  (0.9836 overall, 0.9843 safety/policy/execution, zero unreviewed
  survivors). A later `0ac4335` workflow attempt failed before job creation
  with GitHub internal server errors; Rust route persistence and non-forced
  `init`, configured routing/controls and host discovery now pass local
  parity but await fresh CI.
  The older mutation-status section below is historical.
- The frozen context-band release gate remains 0.6667 < 0.90. The 63-candidate
  two-human annotation/adjudication round is not complete. Synthetic or AI
  labels cannot be submitted as human labels.
- OpenAI Responses API text execution is default-off and requires provider
  opt-in, a ready API host, an auto-approval decision and `execute --yes`.
  No paid live request or deployment has been validated.
- Route price caps now reject non-finite and negative values. Registry prices
  remain unmeasured for bundled seed models, so a valid cap still excludes
  those models rather than assuming they are under budget.

## Historical limitations and studies

## Route controls (Phase P3)

- `--max-price` excludes every seed model today because seeds carry no
  `input_price_per_million`. It filters correctly once real prices land (P1). This is
  deliberate: unpriced models are never assumed under-budget (see AD-3).
- `--privacy local-only` and `--max-estimated-cost` from the spec are not implemented;
  routing is already local-only and cost estimation is not yet wired.

## Still blocked on external inputs

- P1 dynamic catalog refresh for anthropic/openai/google/openrouter needs live
  authenticated APIs and a large mocked-test surface.
- P2 host access verification needs opt-in live network checks; environment-variable and PATH
  presence are the only local signals today.
- P5 measured model profiles need benchmark inference. Current ability scores have
  `ability_source: curated`, not benchmark-derived evidence.

## Historical mutation setup (TASK-010)

- Windows + Python 3.13 did not produce a valid score. `mutmut` 2.4 encountered console encoding
  and test-baseline issues, mutmut 3.x supports Linux/WSL rather than native Windows, and mutatest
  3.1 crashes on Python 3.13 (`random.sample` on a set).
- `.github/workflows/mutation.yml` now runs pinned mutmut 3.6.0 against the bounded critical-module
  selection with explicit timeouts, completeness checks, 0.85/0.95 score gates, survivor review,
  and uploaded evidence. The implementation is complete, but no score is valid until that first
  GitHub-hosted Ubuntu campaign finishes. No local Windows score is claimed.

## Context-band holdout remains public and model-assisted (TASK-009)

- TASK-009 replaces the wording-matched context release gate with a separate frozen final-holdout
  set and reports development versus final-holdout metrics, pre-TASK-004 behavior, confidence
  intervals, per-band recall, and leakage checks. The original 0.90 threshold is unchanged.
- After one development-only revision was frozen, development accuracy/macro-F1 reached 1.0000 while
  the initial final-holdout accuracy was 0.5778 (95% CI 0.4330-0.7103), macro-F1 0.5739. A later
  principled dev-set generalization (M_ACT_ON_EXISTING) raised the shipped rules-active holdout to
  0.6667 (CI 0.5207-0.7864), macro-F1 0.6792 — see the "proven dataset ceiling" note below. Either
  way the 0.90 gate remains failed and canonical release readiness is NO; no final-holdout tuning
  was done.
- The holdout is public repository data and was model-assisted, not independently human-reviewed.
  It is a meaningful paraphrase/generalization regression set, but it is not a private unseen beta
  evaluation and must not be represented as one.
- Context needs are inferred from short prompt text without the referenced files. Some labels,
  especially implied large repositories/documents and terse ambiguous prompts, have annotation
  uncertainty that sampling confidence intervals do not capture.
- **Proven dataset ceiling (TASK-009, decision A).** A dev-only learned classifier was built and
  evaluated once against the frozen holdout alongside rules and hybrid. None reach 0.90:
  rules-only 0.6667 (macro-F1 0.6792), learned-only 0.6889 (macro-F1 0.6613 — lifts large recall
  but collapses medium recall 0.60->0.33), hybrid 0.6444. Learned is not significantly better than
  rules (overlapping 95% CIs) and has a worse macro-F1, so the shipped config stays rules-active
  (`_USE_LEARNED_BAND=False`); the learned model is retained as a tested, packaged, flag-gated
  artifact with pure-Python inference and rule fallback. 24 development cases underdetermine the
  medium/large boundary; closing to 0.90 honestly needs a larger human-labeled dev set or real-file
  context signals, not more hand-rules or holdout-driven tuning. Full study:
  `loop/tasks/TASK-009-context-band-holdout/learned-model-study.md`.
- Line and branch coverage work locally; property tests are Hypothesis-backed when that optional
  dependency is installed.

## Python floor - resolved to 3.10

- A prior draft claimed the minimum Python version had moved to 3.11 while `pyproject.toml` and CI
  still supported 3.10. The documented floor is 3.10 and the CI matrix covers 3.10-3.13.
- Production code must continue to avoid 3.11-only syntax until the owner explicitly changes the
  supported floor.

## Local environment note

- The developer's `~/.agentrouter/registry/models.yaml` may predate the current catalog. Run
  `agentrouter init --force` to reseed; current code backs up edited seed files first.
