# TASK-008 test contract

- Created payload is removed and `skills/agentrouter` is removed only when empty.
- `skills/` and plugin roots are never recursively removed.
- Unrelated siblings and user-modified destination files survive uninstall.
- Force-install backup is restored; if the managed file vanished, the backup is still restored;
  if the managed file was modified later, both the edit and backup remain.
- Repeated uninstall and reinstall-after-uninstall succeed.
- POSIX and Windows-style traversal paths are rejected before any mutation.
- File and directory symlinks/reparse points are rejected and external targets remain unchanged.
- CLI output includes file and directory dispositions; result dictionaries keep stable keys.

