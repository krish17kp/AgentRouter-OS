# TASK-018A — progress

Branch: `task/TASK-018A-api-contract-sdk-compatibility` (from RC `45e1d9e`).
Target: `release/agentrouter-v0.5-rc1`. Not merged to main; nothing tagged,
published or deployed.

## What shipped

**`agentrouter/contract.py`** — canonicalisation, export, baseline loading and
the semantic diff. The contract is `contracts/http/v1/openapi.json`; its
provenance (product version, tool version, source commit, generation time,
operation count) lives beside it in `manifest.json`, deliberately *not* in the
contract, so an unchanged API produces an unchanged file.

**`agentrouter contract export | check`** — hidden maintainer sub-app.
Exit codes: `0` compatible, `1` breaking, `3` missing or untrustworthy baseline.
A missing baseline is a failure, never a pass. `export` refuses to overwrite the
baseline while a breaking change is present; `--accept-breaking --reason "..."`
appends to `accepted_breaking_changes`.

**Server changes that made the gate meaningful.** Four operations were declared
`-> dict`; they now use response models declaring the stable top-level keys with
`extra="allow"`, so the contract can see the fields without the wire losing any.
Auth moved from a bare `X-API-Key` header to a declared `APIKeyHeader` security
scheme.

**Typed errors.** `internal_error` (500) and `registry_unavailable` (503) carry
fixed messages and an `X-Request-ID`; the detail goes to the log at ERROR with a
redacted traceback.

**SDK parity.** `contracts/sdk/capabilities.json` lists nine operations; both
suites drive the real app — Python via in-process uvicorn, TypeScript via
`scripts/serve_for_parity.py` over loopback. CI sets
`AGENTROUTER_REQUIRE_LIVE=1` so a skipped live suite fails instead of passing.

**CI.** New `api-compatibility` job; `enforce-release-gate` now `needs` it.
Top-level `permissions: contents: read` added to `ci.yml` and `security.yml`.

## Findings I fixed during review (each has a regression test)

Backward-compatibility review:

| # | Finding | Fix |
|---|---------|-----|
| 1 | Four operations untyped, so the gate was blind on 4 of 9 | response models with `extra="allow"` |
| 2 | Auth was a bare header, so adding/removing it was invisible | `APIKeyHeader` security scheme |
| 3 | Parameter schemas compared for presence only | `_compare_schema` on `p["schema"]` |
| 4 | Validation constraints not compared at all | `_compare_constraints` (bounds, `pattern`, `additionalProperties`) |
| 5 | Removing a media type undetected | `_compare_media_types` |
| 6 | `servers`, `info.version`, `operationId`, `deprecated` undetected | compared in `diff_contracts` |
| 7 | Introducing a bound where none existed classified as merely "risky" | an absent bound is now the unbounded end of the range, so it compares as the strongest tightening (**breaking**) |

Security review:

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 1 | High | `RegistryError` returned `str(exc)` — the registry path, the offending source line, and any credential pasted into it — to an unauthenticated caller on `/v1/models` and `/ready` | fixed message + `registry_unavailable`; detail logged only |
| 2 | High | `@app.exception_handler(Exception)` was dead code on the outermost middleware, so unhandled faults answered without an envelope or request id, and catching them silently would have hidden the fault from the operator too | convert in `request_id_middleware`; log at ERROR with a redacted traceback |
| 3 | High | An unresolvable/self-referential/remote `$ref` inlined as `{}`, so a one-character baseline edit made a schema look permissive and turned the gate green | `validate_refs`; `load_baseline` refuses such a document |
| 4 | High | `_resolve` expanded fan-out refs exponentially — an OOM on a small document | node + depth budget raising `ContractError` |
| 5 | Medium | `validate_refs` itself re-walked every path: 26 levels of fan-out = 2**26 steps, hanging the check meant to protect CI | memoise validated refs; DFS stack still detects cycles. Contract suite went 66s → 3.5s |
| 6 | Medium | Export followed a symlink at the target and could write outside the root | `_safe_write` containment + symlink refusal |
| 7 | Medium | The acceptance history was erasable by a later routine export, and could record a break the checker never found | append-only history gated on `report.breaking` |
| 8 | Medium | `log_event` wrote unredacted strings | `redact()` applied to all string values |
| 9 | Low | Repo-only tooling shown in user-facing help | `hidden=True` |
| 10 | Low | `contract check` reported "no server extra" with exit 3 and told the user to run `export`, which fails identically | `ServerExtraMissing` → exit 1, no misleading hint |

Also fixed while verifying: the npm tarball shipped tests, including one that
references a repo path absent from the package — `files` now scopes it to
`src` + `README.md` (7 files → 3, 7.2 kB → 2.8 kB).

## Verification

| Check | Result |
|-------|--------|
| pytest | 775 passed, 3 skipped |
| coverage (branch, gate 80%) | 85.32% total; `contract.py` 92% |
| hook tests | 33 passed |
| ruff check / format | clean |
| bandit (`-c pyproject.toml`) | 0 issues, no new `nosec` |
| pip-audit (env + requirements.txt) | no known vulnerabilities |
| secret scan (CI mirror) | 0 flagged outside `tests/`/`.github/` |
| `pytest -m security` | 5 passed, 1 skipped |
| build | wheel + sdist |
| clean wheel, unrelated dir | `contract export` **byte-identical** to the committed contract |
| core-only wheel (no `[server]`) | guidance + exit 1, not a traceback; core CLI unaffected |
| npm typecheck | clean |
| npm test | 18 passed, 0 skipped, with the live app |
| npm test, live app unavailable | 4 skipped, exit 0 — and exit 1 under `AGENTROUTER_REQUIRE_LIVE=1` |
| offline evaluation | invariants hold; `context_band 0.6667` still honestly below the unchanged 0.90 gate |
| critical-module mutation gate | see below |

Nothing was lowered, allowlisted or waived to obtain any of these.

## Honest limitations

- The TypeScript live suite starts a **Python child process**; Node cannot host
  an ASGI app in-process. It is the real app over loopback, not a mock, but it
  is not literally in-process the way the Python suite is.
- `contracts/http/v1/` is versioned `v1`. A deliberate v2 would need a second
  directory and a migration note; the current workflow only records accepted
  breaks against v1.
- `release.yml` still has no top-level `permissions:` block. I left it alone
  deliberately — a release workflow may legitimately need write scope, and
  narrowing it is a release-process decision, not part of this task.
