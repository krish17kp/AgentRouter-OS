# Independent audit

Three read-only reviewers, none the implementer: `verification-engineer`,
`security-reviewer-arros`, `product-architect`. Full findings and
classification are in repairs.md (each finding's fix is recorded there,
per-severity, with reproduction evidence). Summary by severity:

- **CRITICAL / HIGH**: none found by any reviewer.
- **MEDIUM**: 3, from security-reviewer-arros — unenforced `timeout` contract;
  adapter-supplied `detail` not sanitized against control chars/ANSI escapes;
  `_LIVE_CHECKS` keyed inconsistently (host id in `diagnostics.py` vs.
  provider id in `usage.py`/`cli.py`). All three fixed, see repairs.md.
- **LOW**: 2, from security-reviewer-arros — non-OK `Check` without a
  `remedy` (contract violation, fixed); unguarded process-global
  `register_live_check` hook (accepted as-is — not attacker-reachable today,
  since plugin installs are file-copy only with no dynamic Python import; a
  hardening note for whenever in-process extensions exist).
- **Correctness (from product-architect)**: 1 real bug — duplicated
  `excluded` entries in `apply_live_verification` (reproduced, fixed).
- **Design (from product-architect)**: `_LIVE_CHECKS` registry vs. a direct
  per-provider dispatch function — reviewed as a defensible judgment call
  given task.yaml's explicit pluggability requirement and the existing
  `hosts.HostStatus`/`_CLI_HOSTS` precedent for a small typed-state module;
  kept as-is. Single-level re-rank (a live-EXHAUSTED *second* pick is not
  re-checked) — documented with a `ponytail:` comment rather than built out,
  since `_LIVE_CHECKS` is empty in production and the case is unreachable.
- **Minor style (from product-architect)**: `harness.py`'s function-local
  `os` import moved to module level.

verification-engineer independently ran every `verification_commands` entry
in task.yaml and reproduced pass/fail per acceptance criterion — see
release-check.md for the final restated evidence after repairs.
