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
| 10 | Low | `contract check` reported "no server extra" with exit 3 and told the user to run `export`, which fails identically | `ServerExtraMissing` → its own exit code **4** (not 1, which CI would read as a real breaking change), no misleading hint |

Also fixed while verifying: the npm tarball shipped tests, including one that
references a repo path absent from the package — `files` now scopes it to
`src` + `README.md` (7 files → 3, 7.2 kB → 2.8 kB).

## Verification

| Check | Result |
|-------|--------|
| pytest (first round) | 775 passed, 3 skipped — superseded by the second round below |
| coverage (branch, gate 80%) | 85.32% total; `contract.py` 92% |
| hook tests | 33 passed |
| ruff check / format | clean |
| bandit (`-c pyproject.toml`) | 0 issues, no new `nosec` |
| pip-audit (env + requirements.txt) | no known vulnerabilities |
| secret scan (CI mirror) | 0 flagged outside `tests/`/`.github/` |
| `pytest -m security` | 5 passed, 1 skipped |
| build | wheel + sdist |
| clean wheel, unrelated dir | `contract export` **byte-identical** to the committed contract |
| core-only wheel (no `[server]`) | guidance + exit 4, not a traceback; core CLI unaffected |
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
- `contracts/http/v1/` versions the **artifact**, not the API — see AD-5. There
  is one app and one document; a `v2` directory would describe the same app twice
  and orphan the v1 baseline. A real v2 is versioned in the URL space.
- `release.yml` still has no top-level `permissions:` block. I left it alone
  deliberately — a release workflow may legitimately need write scope, and
  narrowing it is a release-process decision, not part of this task.


---

# Second review round (post-PR-#9, after independent security + compatibility reviews)

PR #9 was already green on every CI job when these reviews landed. Green CI was
not treated as evidence: both reviewers reproduced their findings, and so did I
before fixing each one.

## Security review — 2 HIGH, 2 MEDIUM, 3 LOW

| # | Sev | Finding | Fix, and how it was verified |
|---|-----|---------|------------------------------|
| 1 | High | `/ready` is unauthenticated **and** rate-limit exempt, and logged the registry error at ERROR with a traceback. Python's `lastResort` handler writes ERROR to stderr even with no handler configured, so **8 KB per request** of registry path + offending source line + any pasted credential went to the operator's log, with no auth and no rate limit. | `log_api_error(..., detail=False)` for user-data errors: type + remedy only, no message, no traceback. Measured **8016 → 202 bytes/request**, no path, no content, still actionable. |
| 2 | High | `_SECRET_RE` matched 4 vendor prefixes; 16 of 23 real formats passed through (Google, GitLab, Slack, HuggingFace, fine-grained GitHub PATs, AWS *temporary* keys, JWTs, DSN passwords, `password=`). `log_event` skipped non-string values entirely. | Generic detector (keyword adjacency + long high-entropy runs + PEM blocks) and `redact_value` recursion. All 23 formats masked; ordinary diagnostics unchanged. |
| 3 | Medium | **`rm contracts/http/v1/openapi.json` turned 4 breaking changes into a green gate.** My commit message claimed the history was non-erasable; it was not. | CI now also checks the live app against the contract on the **base branch**, which the PR author does not control. Verified locally: vs base → `endpoint_removed`, breaking; vs self-regenerated → clean. |
| 4 | Medium | `validate_refs` could not see a blanked-but-resolvable component. | Covered by the same base-branch check; the honest limit is now stated in AD-5 rather than overclaimed. |
| 5 | Low | `_safe_write` blocked symlinks but not **hardlinks**, and had a TOCTOU window. | `O_NOFOLLOW` + `st_nlink > 1` refusal. My own new test then caught a bug in the fix: `O_TRUNC` emptied the victim *before* the link check ran — truncation now happens only after. |
| 6 | Low | `_MAX_EXPANDED_NODES` was a **per-call** budget, so cost still grew with API size: 73 s from an 11 KB crafted file, scaling linearly with path count. | One budget on `Report`, shared across the whole comparison, plus an independent `_compare_schema` depth ceiling. Measured **73 s → 0.20 s**, flat from 1 to 256 paths. |
| 7 | Low | `contract export` crashed with an unhandled `RecursionError`. | Caught in `load_baseline_file`. |
| 8 | Low | Unbounded, unsanitised echo of `decision_id`. | `_echo`: 64-char bound + control/bidi/zero-width stripping. **5057 → 122 bytes**; CR/LF and U+202E removed; `d_00001` untouched. |
| — | Info | `scripts/` was excluded from the bandit scan. | Added to the CI scan — which immediately found a **HIGH `B613:trojansource`** in my own new sanitising regex, because I had written the bidi ranges as literal characters. Rewritten as escapes. That finding is the argument for the change. |

Also found while fixing #3: **`contract export` treated an *unreadable* baseline as an
absent one**, so corrupting the file bypassed the same refusal that deleting it triggers —
exit 0, baseline silently overwritten. Split into `BaselineMissing` vs `ContractError`;
all four cases (absent / deeply nested / truncated / dangling `$ref`) now behave correctly.

## Compatibility review — 2 HIGH-impact false greens, 3 false reds

| Case | Was | Now |
|------|-----|-----|
| Enum value removed behind `anyOf[$ref, null]` | **not detected** | `enum_narrowed`, breaking |
| Constraint tightened inside `anyOf` | **not detected** | `constraint_tightened`, breaking |
| Auth header renamed `X-API-Key` → `Authorization` | **not detected** | `security_scheme_changed`, breaking |
| `apiKey` → `http bearer` | **not detected** | `security_scheme_changed`, breaking |
| New **required response** field | breaking (false red) | additive |
| Second accepted auth scheme (OR) | breaking (false red) | additive |
| Request gains `null` | breaking (false red) | additive; response gaining `null` is breaking |

`anyOf[T, null]` is what FastAPI emits for **every** optional field, so the fields the
response models were added to protect were previously guarded for presence only.

Separately — and the most serious of all of them — typing the four new response models
made **`/v1/decisions/{id}` return 500 on a persisted decision whose engine payload had
drifted**. Decisions are opaque JSON in SQLite with no schema version, so asserting
today's shape over yesterday's data breaks data the user already has. Reproduced, then
fixed by typing engine-owned fields `Any`; the field *names* are what the checker
protects, and those are unchanged.

## Documentation corrected rather than defended

- AD-5 no longer claims the acceptance history is unerasable. It says plainly that
  `contracts/` is a committed text file, that code review protects it, and that the
  control which does not depend on good behaviour is the base-branch check in CI.
- AD-6 added, explaining why `required` is read per direction and why engine-owned
  payloads stay `Any`.
- `docs/API.md` gained a **"What the checker still cannot see"** section — semantics,
  response `headers`, path-level `parameters`, `webhooks`/`callbacks`, `discriminator`,
  `readOnly`/`writeOnly`, schema-valued `additionalProperties`, and multi-branch unions
  of differing arity.
- `docs/API.md` documents that `contracts/http/v1/` versions the **artifact**, not the
  API: there is one app and one document, and a `v2` directory would describe the same
  app twice while orphaning the v1 baseline. A real v2 is versioned in the URL space.
- The unreachable `unavailable` 503 row was removed; `CHANGELOG.md` records the
  `registry_unavailable` change as breaking for anyone matching on the old code.

## Final verification

| Check | Result |
|-------|--------|
| pytest | **821 passed, 3 skipped** |
| branch coverage (gate 80%) | **85.29%** |
| hook tests | 33 passed |
| ruff check / format --check | clean, 316 files |
| bandit (`agentrouter` **+ `scripts`**) | 0 issues |
| pip-audit (env + requirements.txt) | no known vulnerabilities |
| `pytest -m security` | 5 passed, 1 skipped |
| credential-pattern scan (CI mirror) | 0 outside `tests/` |
| wheel + sdist | built |
| clean wheel, unrelated dir | `contract export` **byte-identical** to the committed contract |
| installed-wheel `contract check` | clean |
| installed-wheel server smoke | health/ready/models/route/dry-run/404/X-Request-ID all correct |
| npm typecheck | clean |
| npm test (live app) | **18 passed, 0 skipped**, 0 temp dirs leaked |
| npm pack | 3 files, 2.8 kB, nothing published |

No threshold was lowered, no test weakened, no mutant allowlisted.


---

# Third review round — the compatibility reviewer found my own fix was incomplete

The second-round fixes were re-reviewed against the complete diff. Four of the five
claimed fixes held. **Fix 5 did not.**

## The one that mattered

`prompt` was still `str | None` on `RouteResponse`, so `/v1/decisions/{id}` **still
returned 500** for a decision persisted when `prompt` was a dict, list or int. I had
fixed the fields I thought of and missed one, which is exactly how this class of bug
survives. The rule now admits no exceptions: **every field on a `_Passthrough` envelope
is `Any`.** Models we actually construct — `HealthResponse`, `ModelSummary`,
`HostStatusResponse`, `FeedbackResponse` — keep real types, because there we own the
values and a type is a promise we can keep.

Verified across nine drift shapes (`prompt` as dict/list/int, `scores` as pairs,
`classification` as a string, `gates` as a bool, `decision_id` as an int, an empty
payload, an unknown future key): **0 non-200**. Live payload still 14 keys.

## Eleven false greens, seven false reds

| Case | Was | Now |
|------|-----|-----|
| Enum **introduced** on a free-form request field | not detected | `enum_introduced`, breaking |
| Enum removed entirely | not detected | `enum_removed`, reported |
| `const` changed (pydantic emits it for `Literal`) | not detected | `enum_introduced`, breaking |
| `allOf` gains a branch (request narrows) | additive — **backwards** | `union_narrowed`, breaking |
| Response type erased to untyped | not detected | `type_erased`, risky |
| OpenAPI 3.1 list-form `type` changed | not detected | breaking |
| `requestBody.required` false → true | not detected | breaking |
| oauth2 `flows` repointed | not detected | `security_scheme_changed`, breaking |
| `additionalProperties` schema tightened | additive | `additional_properties_closed`, breaking |
| Request gains `format: uuid` | risky | breaking, like `pattern` |
| Union branch reorder | breaking ×2 | no change (canonicalised) |
| Request union widened | breaking | additive |
| Response enum narrowed | breaking | additive |
| `4XX` refined into `401/404/422` | breaking | `response_status_refined`, risky |
| `allOf` branch removed (request relaxes) | breaking | additive |

The enum block was the only classifier in `_compare_schema` that ignored the request /
response direction — directly contradicting AD-6's own stated principle.

## The acceptance workflow was a dead end

The reviewer noticed something I had built and never tested end to end: `contract check`
**never read** `accepted_breaking_changes`. It was only ever written. So
`export --accept-breaking` moved the branch baseline and turned the in-branch check
green, while the base-branch check I had just added still reported the same break —
forever. **A change could be accepted and could never merge.**

`check` now reads the manifest in the tree under review and downgrades a break matching a
recorded `(kind, location)` to a new `accepted` severity: reported prominently, does not
fail. Proven end to end — routine export refuses (exit 1) → owner accepts with a reason
(exit 0) → in-branch check passes → **base-branch check passes** → and a *different*,
unrecorded break in the same change still fails (exit 1).

## Documentation corrected again

- **AD-6** claimed "the union is what gets compared" as the reason not to type engine
  payloads. `_unwrap` was added in the *same change* precisely so that is no longer true.
  The claim is removed; the reason stands without it.
- **`docs/API.md`** band table rewritten to state the direction rules explicitly, with the
  new `accepted` band; the "cannot see" list corrected — categories now covered were
  removed, and `not`, parameter `style`/`explode`/`deprecated` and security-scope
  granularity added.
- The **CI job comment** claimed it fails on any break "without an owner-reviewed decision
  recorded in the contract manifest". That was false until this round; now it is true.

## Final battery (third round)

| Check | Result |
|-------|--------|
| pytest | **839 passed, 3 skipped** |
| branch coverage (gate 80%) | **85.53%** |
| hook tests | 33 passed |
| ruff check / format --check | clean, 316 files |
| bandit (`agentrouter` + `scripts`) | 0 issues |
| pip-audit | no known vulnerabilities |
| `pytest -m security` | 5 passed, 1 skipped |
| credential-pattern scan | 0 outside `tests/` |
| wheel + sdist | built |
| clean wheel, unrelated dir | `contract export` **byte-identical** |
| installed-wheel `contract check` | clean |
| npm typecheck | clean |
| npm test (live app) | **18 passed, 0 skipped**, 0 temp dirs leaked |
| npm pack | 3 files, 2.8 kB, nothing published |

## Not covered by this round

The independent **security** re-review hit a session limit before returning its findings.
The second-round security fixes are verified by their own regression tests, but no fresh
adversarial security pass was completed against this final diff. That is a gap, and it is
recorded here rather than papered over.
