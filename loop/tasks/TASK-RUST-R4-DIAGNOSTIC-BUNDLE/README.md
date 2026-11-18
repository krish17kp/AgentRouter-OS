# Rust R4 diagnostic bundle parity slice

Date: 2026-11-11

## Scope

Port the allowlisted diagnostic-bundle contract from `agentrouter/bundle.py`
to the Rust `agentrouter-cli::bundle` probe while preserving the Python release
authority. Bundle artifacts are named explicitly, bounded to 2 MB per text
file, redacted, refuse existing destinations, and never enumerate arbitrary
files. Database inclusion is opt-in and uses the SQLite online snapshot helper;
the README warns that this includes routed task text.

The Python and Rust implementations now withhold every configured environment
value except the resolved `AGENTROUTER_HOME` path. Presence and blankness remain
visible; values such as user identifiers and log paths are not copied into a
shareable bundle.

## Evidence

- Python bundle tests cover secret/task text exclusion, explicit database
  snapshot opt-in, overwrite refusal, symlink refusal, and environment-value
  withholding.
- Rust CLI compatibility tests cover allowlisting, secret/task text exclusion,
  environment-value withholding, database opt-in and snapshot contents,
  existing destination refusal, and symlink destination refusal.
- Rust workspace tests, formatting, and Clippy with warnings denied pass on the
  local Linux host.
- The latest pushed revision's GitHub CI passes Python and Rust jobs on Linux,
  Windows, and macOS. This local bundle/privacy change still needs its own CI
  run after push. The release-promotion evaluation job remains blocked by the
  frozen context-band result (0.6667 against 0.90).

## Limits

This is a partial Rust probe. It does not replace the shipped Python doctor or
bundle entrypoint, and Windows ACL restriction is not implemented by the Rust
probe. Full cross-platform permission parity, command wiring, and release-gate
approval remain open migration work.
