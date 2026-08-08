# TASK-015 progress

Branch: not yet created — implementation is complete in the working tree on
`release/agentrouter-v0.5-rc1`, blocked on a repo-guardrail issue (see below)
before it can be committed to a task branch and opened as a PR.

Status: **implementation, tests, security review + fixes, and clean-wheel
verification all complete.** Nothing committed yet.

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

## Blocked on

`.claude/hooks/pre_tool_guard.py` unconditionally blocks `git commit`/`git
add`/`git push` for any branch, which conflicts with `command.md` §14 and
`AGENTS.md`'s own "Git and autonomy policy" (both explicitly authorize
committing and pushing to the RC/task branch without asking). The owner
opted to fix the hook directly rather than have this session patch it.
Once unblocked: create `task/TASK-015-trusted-catalogs` from
`release/agentrouter-v0.5-rc1`, commit, push, open a PR to the RC, watch CI,
and merge after checks pass (owner already authorized RC merges this
session).
