# TASK-008 plan

1. Lock the destructive boundary with failing tests for modified files, unrelated siblings,
   empty-directory cleanup, idempotency, reinstall, backups, traversal, and links/reparse points.
2. Add centralized relative-path and destination validation used by plan/install/uninstall.
3. Make install preflight backup collisions and non-file destinations before writing.
4. Make uninstall content-aware: remove only the bundled payload, restore a valid backup, preserve
   modified/unknown content, then call non-recursive `rmdir` only for declared cleanup directories.
5. Run focused tests, security review, full regression, clean-wheel/plugin lifecycle, and docs.

Rollback: the change is additive around the existing result-list API. If a safety check cannot
prove ownership, it preserves the path and reports why.

