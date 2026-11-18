# Rust dependency audit — 2026-11-17

## Reproduction

```console
cargo audit --no-yanked
```

## Result

The local audit scanned 205 locked crate dependencies using the RustSec
advisory database loaded on 2026-11-17. No vulnerability advisories were
reported and the command exited successfully. One unmaintained-dependency
warning was reported for `chrono` (`RUSTSEC-2026-0543`); RustSec currently
lists no fixed upgrade. This warning is non-vulnerability debt and remains
visible rather than suppressed.

The same checkpoint also passed the locked release build:

```console
cargo build --release --locked --workspace
```

The optimized workspace build completed successfully, and the release binary
reported `agentrouter 0.5.0rc1` with the unified command help surface.

## Follow-up

Keep the `chrono` warning on the dependency watch list. Re-run this audit when
the advisory database or lockfile changes; do not claim a zero-warning audit
until a maintained replacement is available and verified across the supported
platforms.
