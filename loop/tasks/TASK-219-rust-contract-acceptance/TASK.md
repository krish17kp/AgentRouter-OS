# TASK-219 — Rust contract export acceptance workflow

## Objective

Bring the Rust contract exporter in line with the documented Python workflow
for intentionally breaking HTTP contract changes, without weakening the
default refusal or filesystem safety controls.

## Acceptance

- routine Rust exports still refuse detected breaking changes;
- `--accept-breaking --reason TEXT` is required to record an intentional break;
- the manifest keeps prior acceptance history and records the exact checker
  findings, reason, and product version;
- manifest updates use the existing no-follow, hardlink-safe atomic writer;
- JSON output reports the number of newly recorded acceptance entries;
- focused unit and CLI smoke tests pass with strict Clippy.
