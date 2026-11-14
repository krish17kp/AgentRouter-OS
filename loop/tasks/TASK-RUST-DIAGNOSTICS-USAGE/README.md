# Rust doctor quota checks

Date: 2026-11-11

## Scope

Align the Rust doctor's opt-in `--verify-live` checks with Python diagnostics.
The Rust probe now asks `agentrouter-hosts::detect_host` whether each API host is
available, resolves the provider through the shared host mapping, and calls the
bounded `agentrouter-usage::check_usage` state machine. This removes duplicated
environment-variable guesses and keeps authentication/provider mapping in one
place. Unauthenticated hosts are not queried; unsupported, exhausted, and error
states remain explicit and never include credential values.

The test harness now clears all provider-key variables before each probe, then
sets only the credentials required by a given case.

## Evidence

- All nine Rust doctor compatibility cases pass, including opt-in usage,
  credential-value redaction, broken registry/database reporting, and bundle
  safety.
- Full Rust workspace tests, Clippy, rustfmt, Ruff, and diff checks pass.
- Full Python regression passes: 1,711 passed, 6 skipped; 90.99% line / 85.19%
  branch coverage.
- The usage verifier has no live provider adapter registered. With a detected
  credential, it honestly reports unsupported until one is implemented.

## Limits

The overall Rust diagnostics surface remains partial: plugin diagnosis,
optional-server detection, full contract metadata, and Python-specific runtime
checks do not have complete Rust equivalents. The current change improves only
the host authentication and usage-state path.
