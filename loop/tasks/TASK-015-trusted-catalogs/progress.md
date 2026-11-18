# TASK-015 progress

Branch: `task/TASK-015-trusted-catalogs` (from `release/agentrouter-v0.5-rc1`)
— **MERGED to the RC via PR #6** (merge commit `8661629`), task branch deleted
local + remote. Post-merge RC CI green: CI, Critical Mutation Testing and
Security all succeed.

Status: **DONE.** Implementation, tests, security review + fixes, docs and
clean-wheel verification all complete and merged.

## Delivered

- `agentrouter/refresh.py`: `write_generated_registry` emits a top-level
  `provenance` block (provider, source_url, fetched_at UTC, count,
  tool_version, cli_args) and writes atomically via `tempfile.mkstemp` (same
  directory) + `os.replace`, with cleanup on any failure. Added
  `previous_model_ids` for deprecation-candidate diffing.
- `agentrouter/cli.py`: `providers refresh` reports candidate deprecations
  (report-only, never deletes) and passes `cli_args` through; new `providers
  restore <provider>` and `providers doctor` subcommands.
- `agentrouter/catalog_ops.py`: `read_provenance`, `deprecations`, hardened
  `rollback` (collision-safe backup rotation, symlink-safe exclusive create)
  and new `restore`; `CatalogError` + `_load_raw` so a corrupt generated file
  fails cleanly everywhere instead of crashing with a traceback.
- `agentrouter/registry.py`: `_load_yaml` now also catches
  `UnicodeDecodeError` (previously crashed `agentrouter route` on a
  non-UTF-8 generated catalog — a pre-existing gap surfaced by this task's
  security review, fixed since it's the same corruption class `doctor`
  exists to catch).
- Docs: `CLI_SPEC.md`, `USER_GUIDE.md`, `MODEL_REGISTRY_SCHEMA.md`,
  `CHANGELOG.md` updated for the new commands and provenance block (these
  hadn't been updated for TASK-013's `status`/`rollback` either — folded in).

## Security review (security-reviewer-arros, this session)

Independent review found 0 CRITICAL, 3 MEDIUM, 2 LOW, 2 INFO. All MEDIUM/LOW
fixed and covered by new regression tests, then re-verified against the
reviewer's own reproduction steps:

- **Predictable temp filename + symlink-following writes** (refresh.py temp
  file, catalog_ops.py backup copy) — fixed via `tempfile.mkstemp` (refresh)
  and an `O_CREAT|O_EXCL` exclusive-create helper (rollback backup); both
  refuse to follow a pre-planted symlink. Verified: a planted dangling
  symlink at the `.bak` path is rotated aside, never dereferenced; an
  out-of-tree victim file is untouched.
- **`providers doctor`/`status`/`route` crash with a traceback on real
  corruption** (non-dict YAML root, non-UTF-8 bytes) instead of failing
  cleanly — fixed via `catalog_ops.CatalogError`/`_load_raw` and a
  `registry._load_yaml` UnicodeDecodeError catch. Verified: `doctor` now
  prints `[FAIL]` + exit 3, `status` prints a clean message + exit 3,
  `route` prints `Registry error: ... not valid UTF-8` + exit 3 (previously
  exit 1 with a raw traceback in all three).
- **Backup rotation silently destroys history on same-second collisions** —
  fixed via a nanosecond clock + collision-probe loop in `_rotate_backup`.
  Verified: 5 rapid rollback/refresh cycles now preserve all 5 backups
  (previously only 2 of 3 survived in a manual same-second repro).
- **LOW: unvalidated `provider` argument in rollback/restore** — added a
  `[A-Za-z0-9_-]+` allowlist (`_validate_provider`), defense in depth (not
  exploitable as written, per the reviewer, since the fixed `models.` prefix
  blocks traversal today).
- **LOW: unsanitized provenance echoed to the terminal** — `read_status` now
  strips non-printable characters from `source_url` before it reaches
  `summary`/`doctor` output.
- Two INFO items (unbounded rotated-backup accumulation; atomic-write
  guarantees don't cover power loss, only crash/kill) accepted as documented
  limitations, not fixed — bounded impact, out of this task's scope.

## Verification (this session)

- `pytest -q`: 629 passed, 3 skipped (local, ~30s).
- `ruff check .` / `ruff format --check .`: clean.
- `bandit -c pyproject.toml -r agentrouter`: 0 issues.
- Clean-wheel: built, installed into a fresh venv outside the repo,
  `providers status/doctor/rollback/restore` and `route` all exercised from
  the packaged wheel — pass. Re-run after the security fixes — still pass.

## Guardrail repair (owner-authorized, shipped in this PR)

`.claude/hooks/pre_tool_guard.py` blocked `git add`/`commit`/`push`
unconditionally, contradicting `command.md` §14 ("You may: ... commit verified
work; push to the current release/task branch") and the `AGENTS.md` git policy
— which made the documented per-task loop impossible to execute. The owner
authorized a narrow repair, now branch-aware rather than absolute:

- `git add` / `git commit` — only on a `task/*` branch;
- `git push` — only from a `task/*` branch, only for that same branch
  (`-u`/`--set-upstream` fine), never forced, never targeting a protected
  branch.

Still refused: every git write on `main` and `release/*`, force push,
remote-branch deletion, tags, history rewriting, `reset --hard`, `git clean`,
recursive deletes, DB destruction, deployment, publication, `shell=True`,
permission bypass and secret printing. 33 hook tests cover the allow/block
matrix, including that shell redirections (`2>&1`, `> file`) are not parsed as
push refspecs and cannot be used to smuggle a protected target.

## Merge

PR #6 -> `release/agentrouter-v0.5-rc1`, merge commit `8661629`, 2026-08-08.
All checks passed (test matrix 3.10-3.13, test-windows, build-smoke, Security
scan, release-readiness-report, critical-modules mutation gate);
`enforce-release-gate` and `live-smoke` correctly skipped on a task->RC PR.
Task branch deleted local + remote.
