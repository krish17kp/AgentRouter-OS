# Known Limitations

## Current migration and release limits (2026-11-14)

- The Rust evaluation crate now matches the full `agentrouter/evaluation/adapters/agentrouter_gold.py` module surface: metadata, availability, describe, loading, checksum and deterministic sampling. Its Python/Rust differential test covers all 165 committed cases plus Unicode/default handling. External adapter base behavior and the other dataset adapters remain Python-only; see `docs/RUST_PARITY_MATRIX.md`.
- A Rust fixture-mode adapter base now covers metadata, availability, description, JSONL loading/checksums, deterministic sampling, and explicit real-mode skips for six external fixtures. Real dataset downloads and dataset-specific row transformations still require Python's optional `datasets` integration.
- Python is still the shipping router. Rust R4 has route, SQLite,
  stored-decision, prompt, and feedback compatibility probes, but no complete
  public Rust CLI/HTTP/MCP replacement. R5–R13 remain open.
- Plugin mutation testing on `984db4b` passes locally (1,629 selected mutants,
  0.9693 overall, 0.9663 safety/policy/execution, 0.9815 routing, zero
  unreviewed survivors); its currently reported PR checks are green.
- The Rust init probe uses directory-handle-relative seed writes and rejects
  existing linked SQLite targets. SQLite still canonicalizes and reopens the
  database by path; a concurrent leaf or ancestor swap can redirect that open.
  Linux's proc-fd path helps after a swap before connect, but is not a complete
  race-safe SQLite strategy. This is an R4 production blocker.
- The Rust diagnostic-bundle probe now has an allowlisted file set, redaction,
  bounded text artifacts, and opt-in SQLite snapshot support. This local slice
  withholds non-home environment values in both Python and Rust and has focused
  tests; full CLI parity, Windows ACL restrictions, and cross-platform CI for
  this change remain open.
- Rust provider-status parity is a new probe, not full `providers` CLI parity.
- Rust plugin install now handles missing and byte-identical files without
  replacement and writes Python-readable ownership state. Forced replacement,
  managed upgrades, transaction recovery, and Rust uninstall remain Python-only.
-  The path-format and CPython file-identity fixes pass hosted Rust and
  Python/Rust jobs on Linux, Windows, and macOS at `f81d2d1`; Windows and macOS
  Python CI also pass.
- Rust annotation manifest integers now preserve arbitrary precision exactly
  in schema validation and JSON storage under TASK-111. Datetime grammar and
  remaining Pydantic scalar coercions still keep that schema module Partial;
  hosted validation of TASK-111 is pending.
- Latest full Python coverage is 92.85% statement / 88.68% branch / 91.90%
  combined, meeting the unchanged 90%/85% thresholds; see
  `docs/COVERAGE_REPORT_2026-11-14.md`.
- The frozen context-band release gate remains 0.6667 < 0.90. The 63-candidate
  two-human annotation/adjudication round is not complete. Synthetic or AI
  labels cannot be submitted as human labels.
- OpenAI Responses API text execution is default-off and requires provider
  opt-in, a ready API host, an auto-approval decision and `execute --yes`.
  No paid live request or deployment has been validated.
- Route price caps now reject non-finite and negative values. Registry prices
  remain unmeasured for bundled seed models, so a valid cap still excludes
  those models rather than assuming they are under budget.
- macOS Python/Rust CI is now configured and passed on PR #28.

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

## Windows reparse-point handling in the plugin installer is unverified (TASK-019)

`agentrouter/plugins.py` removes a verified directory through two different code
paths: `O_NOFOLLOW`/`dir_fd` with `(st_dev, st_ino)` verification on POSIX, and
`CreateFileW` with `FILE_FLAG_OPEN_REPARSE_POINT` on Windows.

The adversarial suite proves the POSIX path. It proves **nothing** about the
Windows one — they are different code, and a Linux symlink test is not evidence
about an NTFS junction. `tests/test_plugins_platform.py` skip-marks the
Windows-only assertions so they can only pass where a Windows runner executes
them; the CI matrix does include `test-windows`, but the link-specific attacks
cannot be expressed portably and are not attempted there.

Concretely: on Windows, treat "refuses reparse points" as designed-for and
partly exercised, not as proven. Closing this properly needs junction and
symlink attack tests written against Windows semantics.

Branch coverage of `plugins.py` is also capped on Linux for the same reason:
roughly 70 of its 818 statements are the Windows `ctypes` branch, so a Linux run
cannot exceed about 91.4%.

## Local environment note

- The developer's `~/.agentrouter/registry/models.yaml` may predate the current catalog. Run
  `agentrouter init --force` to reseed; current code backs up edited seed files first.
