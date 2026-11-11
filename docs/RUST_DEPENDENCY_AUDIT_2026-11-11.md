# Rust dependency audit — 2026-11-11

## Reproduction

```console
cargo audit --deny warnings
```

## Result

The local audit completed with no vulnerability or warning findings across 160
locked crate dependencies after incorporating the merged OpenAI transport. The scan used the RustSec advisory database fetched
on 2026-11-11. Workspace unit tests and Clippy also pass locally after the
dependency changes; CI still must confirm Linux, Windows, macOS, and Rust 1.89.

## Remediations

- `rusqlite` moved to 0.41.1 / `libsqlite3-sys` 0.39.1, which bundles SQLite
  3.54.1. This fixes the local-database-plus-WAL memory disclosure in
  [RUSTSEC-2026-0459](https://rustsec.org/advisories/RUSTSEC-2026-0459.html).
  The patched crate declares Rust 1.89, so the workspace minimum and CI job
  were raised from 1.75 to 1.89.
- `serde_yaml` 0.9 depended on unmaintained `unsafe-libyaml`. The Rust workspace
  now uses the serde-compatible `noyalib-serde-yaml` 0.0.60 layer. An initial
  0.0.29 resolution was caught by audit as
  [RUSTSEC-2026-0333](https://github.com/sebastienrousseau/noyalib/pull/470),
  so the dependency was raised to its patched 0.0.60 release before committing.

This is a snapshot of the lockfile and advisory database on the date above;
repeat the command as dependencies or advisories change.
