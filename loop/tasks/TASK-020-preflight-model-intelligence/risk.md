# Risk

**Compatibility**: low. Every change is additive (new opt-in CLI flags, new
optional JSON key, one new always-on `doctor` check id). `route`'s JSON
contract gains `usage_check` only under `--verify-live`; nothing removes or
renames an existing field. Not a public HTTP/SDK contract change (REST API,
`contract.py`, TypeScript SDK untouched — a deliberate scope cut, reviewed by
product-architect as defensible since the CLI/API already diverge more than
this change adds, e.g. `server/service.py`'s route call already omits
controls/adapted-weights the CLI applies).

**Privacy**: none. No new telemetry, no new network call by default. The one
network-capable code path (`usage.check_usage(..., live=True)`) is inert in
production (`_LIVE_CHECKS` is empty) and only ever activates behind an
explicit `--verify-live` flag the user typed.

**Security**: addressed via the repair loop (repairs.md) — unenforced
timeout, unsanitized adapter output, and an inconsistent provider-id
namespace were all found by independent review and fixed before this task
closed. Residual, accepted: `register_live_check` is an unguarded
process-global hook, not attacker-reachable today since plugin installs are
file-copy only (no dynamic Python import) — revisit if that ever changes.

**Performance**: `doctor` (no flag): unaffected, `check_harness()` is a
handful of `os.environ.get()` calls. `doctor --verify-live` /
`route --verify-live`: bounded by `timeout` (default 5s) per provider,
enforced by a real wall-clock mechanism (not just a parameter passed
through and trusted) — see repairs.md #2. Measured on this machine: fresh
`doctor` 1.13s, `doctor --verify-live` 0.98s (all providers UNSUPPORTED —
no network I/O actually occurs since no adapter is registered).

**Mitigations already in place, not deferred**: failure isolation
(`_safe()` wraps every check; one broken provider can't crash `doctor`),
secret redaction (presence-only, traced through every new string sink),
sanitization of any live-check-returned text before it reaches a sink.
