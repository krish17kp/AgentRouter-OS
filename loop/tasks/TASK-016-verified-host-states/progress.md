# TASK-016 progress

Branch: `task/TASK-016-verified-host-states` (from `release/agentrouter-v0.5-rc1`
@ `8661629`, i.e. after TASK-015 merged).

Status: **DONE — MERGED to the RC via PR #7** (merge commit `5847c22`), task
branch deleted local + remote. Post-merge RC CI green: CI, Critical Mutation
Testing and Security all success.

## Mutation gate: failed, then repaired honestly

The first CI run failed `critical-modules`: the new detection code added mutants
the suite did not kill, dropping `safety_policy_execution` to **0.8895** (target
0.95) with **72 unreviewed survivors**. Repaired with real tests, not allowlist
entries or a lowered threshold — 30 exact-value tests over every branch, state
constant, reason, remedy and helper return in the new code, plus `.host`
assertions (their absence is exactly what let the `host -> None` mutants live),
the generic `_AUTH_HINT` fallback via an injected CLI host with no curated hint,
and the execute-refusal path that carries no remedy.

One assertion was itself the bug: a substring check let the `"XX...XX"`-wrapped
message mutant survive, because the wrapped text still contains the original.
Now matched as an exact line.

Verified by reproducing the campaign locally (mutmut 3.6.0, same runner and
flags as CI, 1057 mutants) before pushing: **overall 0.9858,
safety_policy_execution 0.9877, routing_engine 0.9815, 0 unreviewed survivors,
all five gates PASS** — then confirmed green on CI.

## Delivered

- `agentrouter/hosts.py`: a readiness `state` vocabulary from command.md PHASE C
  — `missing` / `installed` / `configured` / `authenticated` / `authorized` /
  `degraded` / `unknown` — plus a per-host `remedy` (the concrete next step).
  `availability` is unchanged in meaning and is now *derived* from the state via
  `_availability_for`, so routing, `execute` gating and `models list --available`
  behave exactly as before for every previously-supported input.
  - CLI hosts: `shutil.which` (which already filters on `X_OK`), then
    existence-only checks of the host config dir and credential file, then env
    fallbacks.
  - API hosts: unset -> `missing`, set-but-blank -> `degraded`, set ->
    `authenticated`.
  - `_home_dir()` indirection so tests are hermetic and cross-platform (CI runs
    a Windows job; monkeypatching `HOME` alone would not work there).
- `agentrouter/cli.py`: `hosts list` / `hosts doctor` / `hosts show`, the `setup`
  wizard and the `execute` refusal path all report the state and remedy.
  `hosts doctor` now ends with either "Ready to execute: <hosts>" or the closest
  concrete fix, and still exits non-zero only when no real host is ready
  (`manual` alone does not count).
- REST/MCP: `service.list_hosts` and `HostStatusResponse` gained additive
  `state` / `remedy`; `execution_route_block` gained `host_state` / `host_remedy`
  and a per-entry `state` in `all_hosts`. All additive — existing keys untouched.
- Docs: new USER_GUIDE section 8 (`hosts`) with the state table and the honesty
  note about `authorized`; CHANGELOG Added + Fixed entries.

## Bug found and fixed

Host detection tested the API-key env var for truthiness, so a **set-but-blank**
key (`OPENAI_API_KEY="   "`) reported `available`. `execute` would then treat the
host as runnable and attempt to run against a credential that cannot possibly
authenticate. Reproduced before the change, now reports `degraded` / unavailable
with a fix-it message, and is pinned by a parametrised regression test over
`""`, `"   "`, `"\t"`, `"\n"`.

## Honesty constraint

`authorized` means a real authorization check succeeded. That needs the opt-in
live call PHASE C lists separately and which is **not implemented**, so no
offline path returns it — asserted by `test_offline_detection_never_claims_authorized`
(which sets up every credential it can and still requires the state to differ)
and by a REST-payload assertion. `authenticated` is documented as "a credential
exists", never "the provider accepted it".

## Security review (security-reviewer-arros) and repairs

Independent review: **0 critical, 1 high, 1 medium, 3 low, several info.** Every
high/medium/low finding is fixed and pinned by a regression test; each fix was
re-verified against the reviewer's own reproduction.

- **HIGH — new unhandled `PermissionError`/`OSError` crash.** TASK-016 introduced
  the first filesystem access into `detect_host`; `Path.exists()`/`is_dir()`
  propagate `EACCES`/`ENAMETOOLONG`, so a container or NFS `HOME` the user cannot
  traverse turned `hosts doctor`, `hosts show`, `route` and the REST
  `/v1/hosts` endpoint into a raw traceback (an unhandled 500 on the API).
  Pre-TASK-016 detection could not raise at all, so this was a genuine
  regression. Fixed with `_safe_exists`/`_safe_is_dir`, which fall through to
  "no evidence". Reproduced the reviewer's scenario (mode-000 HOME) before and
  after: CLI now exits 0 and `service.list_hosts()` returns normally.
- **MEDIUM — a blank env var overrode a working CLI login.** The `env_fallback`
  blank check ran before the config-dir check, so `ANTHROPIC_API_KEY=` (common
  from docker-compose/.env) plus keychain-based `claude login` reported
  `degraded`/unavailable and refused to execute. Evidence is now ordered
  positive-first (credential file, then a real env key, then config dir), and a
  blank fallback only matters when there is no other evidence.
- **LOW — registry-controlled `required_command` echoed unsanitized.** A crafted
  value could emit ANSI escapes and forge an "authenticated" readiness line —
  precisely the signal this feature exists to convey. Now sanitized and length-capped
  before display.
- **LOW — non-hermetic mutation-kill test.** `test_execution_route_block_payload_keys_and_values`
  patched neither `_home_dir` nor `OPENAI_API_KEY`, so a clean CI runner with a
  set-but-blank key would fail it; it passed here only because this machine has
  `~/.codex/auth.json`. Made hermetic. Also replaced a self-referential
  `all_hosts` assertion (which pinned nothing) with literals and removed a
  duplicated assert.
- **LOW — "closest fix" was really "first in `known_hosts()` order"**, so doctor
  could tell you to install a whole CLI when exporting one variable would do.
  Now ranked by remediation cost via `hosts.fix_cost` and relabelled "Easiest fix".
- **INFO — `installed` displayed `[OK]` while telling the user to install.**
  Split the hint tables: `_INSTALL_HINT` (binary absent) vs `_AUTH_HINT`
  (present but unauthenticated), so an installed-but-unauthenticated host now
  says "run: claude login".

Reviewer-verified clean, no action needed: secret handling (audit hook recorded
**zero file opens** during detection and no credential fragment in any output
field); gate monotonicity (exhaustive 4320-case old-vs-new differential found
**0 cases more permissive**, 912 strictly stricter — all blank-key cases);
`authorized` never constructed (AST walk of all 13 construction sites); no
network, no subprocess; hostile symlinks at the credential path are inert
because the code only stats. Bandit 0 issues with no new `nosec`; pip-audit clean.

## Guardrails honoured

No routing/threshold/gate change; frozen holdout untouched; no network call on
any detection path; no credential value read or printed (existence checks only).

## Verification

- `pytest -q`: **660 passed, 3 skipped** (30 new in `tests/test_host_states.py`).
- `.claude/hooks/test_hooks.py`: 33 passed.
- `ruff check` + `ruff format --check`: clean. `bandit`: 0 issues.
  `pip-audit -r requirements.txt`: no known vulnerabilities.
- Clean wheel: built, installed into a fresh venv outside the repo; `hosts doctor`
  renders states + remedies, the blank-key case reports `degraded`, and `route`
  still works.
- Updated three `tests/test_mutation_kills.py` assertions that pinned the old
  strings/payload, keeping their exact-value mutation-killing precision and making
  the CLI-host test hermetic (it previously depended on whether the machine
  running the suite happened to have `~/.codex`).
