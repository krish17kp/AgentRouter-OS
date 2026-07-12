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

## Reporting a vulnerability

Open a GitHub issue **without** exploit details and ask for a private contact,
or use GitHub's private vulnerability reporting on the repository. Please do
not publish proof-of-concept exploits before a fix is available.
