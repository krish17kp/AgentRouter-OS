# Security Policy

## Secrets

- **No secrets in this repo.** `.env.example` contains placeholders only.
- The app reads keys from **shell environment variables** — it does not
  auto-load `.env`. `.env`/`.env.example` are a reference template you can
  `source` yourself; real keys live in your shell environment, never in
  tracked files, code, or YAML registries.
- If you set `OPENROUTER_API_KEY`, it is sent as an HTTP auth header only and
  is never printed or logged (enforced by a test).
- `providers refresh openrouter` runs **keyless** — the catalog endpoint is
  public, so no credential is required at all.
- If a key is ever committed by accident: rotate it immediately at the
  provider, then remove it from the file. Rotation is the fix; deleting the
  commit is not enough (history is public).

## Design-level safety

- **Planner, not executor:** the CLI never runs the recommended tool or
  executes any task. `supports_execution` is `false` for every adapter.
- **High-risk tasks are human-gated:** anything touching auth, credentials,
  payments, production, or deletion is classified high-risk and marked
  `human-approval-required` — auto-execution is disallowed by the safety
  engine (tested).
- **Local-only data:** decisions are logged to a local SQLite file. Nothing
  leaves your machine except the optional, explicit `providers refresh` call
  to the provider's public catalog endpoint. Use `route --no-log` for
  sensitive task text.

## Plugin installation (TASK-019)

`agentrouter plugin install` writes into user agent-configuration directories
**outside this repository** (`~/.claude`, `~/.codex`) and `uninstall` removes
files from them. That makes it the most privileged filesystem operation in the
product, so its guarantees are stated exactly, and each one is backed by a test
that attacks it rather than by a claim in a docstring.

**Guaranteed, and proven on POSIX** (`tests/test_plugins_adversarial.py`):

- a destination that is a symlink, a dangling symlink, or has more than one hard
  link is **refused**, and the file it points at is left untouched;
- a symlinked **parent directory** is refused, so a write cannot be redirected
  out of the plugin root;
- `..`, absolute paths and traversal in a plugin's declared destination are
  rejected before any filesystem access;
- uninstall **never** deletes a file it cannot prove it installed: a file the
  user edited, a file that was never ours, or any file when the ownership
  record is missing or unreadable, is preserved and reported;
- cleanup removes only a directory AgentRouter created and left empty, verified
  by `(st_dev, st_ino)`; a directory containing anything else is preserved;
- a package upgrade over a user-edited file is refused, not silently applied;
- displacing a file with `--force` always writes a backup first, and a colliding
  backup aborts the install rather than overwriting it;
- concurrent installs, and concurrent install/uninstall, serialise; they do not
  corrupt state or leave a partially written file;
- a plugin name echoed back in an error is bounded to 64 characters and stripped
  of every character Python treats as a line boundary, plus the control, bidi and
  zero-width ranges — so a hostile name cannot forge a line that looks like
  AgentRouter spoke it, in a terminal or in captured output.

**Not guaranteed — platform-dependent.** `_remove_directory_by_handle` has two
different implementations. The POSIX one uses `O_NOFOLLOW`/`dir_fd` with identity
verification. The Windows one uses `CreateFileW` with
`FILE_FLAG_OPEN_REPARSE_POINT`. **The POSIX tests say nothing about the Windows
branch.** Windows reparse-point and junction behaviour is exercised only by the
skip-marked tests in `tests/test_plugins_platform.py`, and only when a Windows
runner actually executes them. Until then it should be treated as unverified.

**Failure behaviour.** Every failure raises a typed error with an actionable
remedy — including a full disk, which previously escaped as a raw `OSError` and
gave the user a traceback with no message. `agentrouter plugin doctor` reports
the state of each destination and the exact safe fix; it never suggests deleting
an arbitrary directory, and never prints file contents, because its output is
meant to be pasteable into a support request. It is read-only: running it leaves
the filesystem byte-for-byte unchanged, verified on both a clean and an installed
home directory.

`plugin list` and `plugin doctor` also survive the states they exist to report.
Both previously died with a raw traceback when a destination path contained a
symlink — the refusal that protects the write path escaped into the display
path — so the two commands a user reaches for when their plugin directory has
been tampered with were the two that failed. They now report `blocked` and print
the offending path with its remedy.

## Reporting a vulnerability

Open a GitHub issue **without** exploit details and ask for a private contact,
or use GitHub's private vulnerability reporting on the repository. Please do
not publish proof-of-concept exploits before a fix is available.
