# TASK-216 — Rust public contract export

## Objective

Expose the existing safe Rust OpenAPI canonicalization/export primitives through
the unified `agentrouter contract export` command so the public Rust CLI can
create a baseline instead of stopping at check/diff probes.

## Acceptance

- `agentrouter contract export` accepts an optional read-only `--source PATH`;
- missing baselines can be created and existing baselines refuse detected
  breaking surface changes;
- output supports `--json` and deterministic `--generated-at` evidence;
- unreadable or malformed baselines fail closed;
- the command remains explicit that the committed Rust OpenAPI artifact is the
  source when `--source` is omitted; live framework schema generation remains
  a separate parity limitation.
