# TASK-248 — Prompt output parity

## Objective

Complete the Rust `prompt generate --from` output contract for the public
unified CLI and direct compatibility probe.

## Evidence

- `--tool` is forwarded as a named option and `--out PATH` writes the exact
  Python-generated execution prompt.
- Output files are opened with no-follow semantics and hard-linked files are
  rejected before overwrite.
- Public unified and direct process regressions cover file output; the focused
  decision/unified CLI selection passes 42 tests.
- The Rust CLI crate remains green at 89 tests with strict Clippy, formatting,
  and diff checks.
