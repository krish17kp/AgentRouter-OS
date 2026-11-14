# Test-first contract

**Positive**: harness detection names Claude Code from real `CLAUDECODE`
evidence and CI from `CI`/`GITHUB_ACTIONS`; a registered live-usage adapter
can report AVAILABLE/EXHAUSTED with real evidence; `route --verify-live`
re-ranks away a live-EXHAUSTED top pick and explains why.

**Negative**: an adapter that raises, hangs past its timeout, or returns a
malformed result is isolated to `ERROR`, never propagated, never crashes
`doctor`/`route`.

**Boundary**: empty environment (harness UNKNOWN); GITHUB_ACTIONS/CI set to
the literal string `"false"` (must not read as truthy); no recommendation to
re-rank (`apply_live_verification` is a no-op on `None`); unregistering a
check restores UNSUPPORTED.

**Security**: an env var value is never echoed into a Check summary or
harness evidence string; an adapter-supplied `detail` string with ANSI
escapes/control characters/oversized length is sanitized and truncated before
it can reach stdout, JSON, or the SQLite decision log; a fake API key is
asserted absent from `doctor`/`doctor --verify-live` output; `--verify-live`
default-off is asserted to make zero network calls (no urllib/requests/socket
import in either new module, confirmed by a fresh reviewer's independent
read, not just this file's own claim).

**Compat**: `route`'s JSON payload has no new key without `--verify-live`;
existing `doctor`/`route`/`hosts`/`diagnostics` suites (936 tests) stay green
untouched.

**Packaging**: not touched by this change — no new dependency, no new package
data, no `pyproject.toml` edit.

**Customer**: `doctor`/`doctor --verify-live`/`route --verify-live` smoke-run
against a real fresh `agentrouter init` home (not just CliRunner) — see
release-check.md.

**Benchmark**: not applicable — no scoring/complexity logic was added; the
existing benchmarked routing behavior (`weights_for`, `score_models`) is
unmodified except for gaining one additional exclusion source
(live-EXHAUSTED), which only fires when `--verify-live` is passed.
