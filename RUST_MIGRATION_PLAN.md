# Rust Migration Plan

> Companion to [AD-7 in ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md#ad-7--approved-rust-native-target-phased-behind-the-existing-contracts).
> The **Python implementation in `agentrouter/` is the current, shipping system**
> and remains release-gated exactly as today. This document plans a phased,
> contract-preserving port to a Rust-native implementation. No Rust code exists
> yet; no Python code is deleted as part of this plan. See
> `AGENTROUTER_FOUNDATION_REVIEW.md` (session artifact, not committed) for the
> inventory this plan is built from.

## Non-negotiables carried over unchanged

- CLI contract (`CLI_SPEC.md`), HTTP contract (`contracts/http/v1/`), MCP
  tool/resource names, the registry YAML schema, and the SQLite decision-log
  schema are **preserved exactly**. A Rust component is only considered a valid
  replacement for a Python one once it passes the *same* compatibility suite
  the Python component is gated on today.
- The seven evaluation gates (`loop/QUALITY_GATES.yaml`) are the release
  authority regardless of implementation language. A ported scorer must
  reproduce bit-identical numbers on the frozen 45-case holdout before it may
  replace the Python scorer as gate authority — "close enough" is a failed
  migration step, not a passing one.
- Mutation thresholds (95% safety/policy/execution, 85% elsewhere) continue to
  apply; `cargo-mutants`/`cargo-audit` are the candidate Rust tools but their
  thresholds must be independently re-validated, not assumed equivalent to the
  current `mutmut`/`bandit` baselines.
- No AI may annotate or adjudicate the frozen holdout, in either language. This
  policy is implementation-independent (see `TASK_012_OWNER_ACTIONS.md`).

## Module-by-module plan

Ordered by the risk/coverage inventory in the foundation review. Each row names
the acceptance test that must pass before the Rust module can be considered
done, and the rollback criterion if it cannot.

| Module (Python) | Port order | Acceptance test | Rollback criterion |
|---|---|---|---|
| `engine.py` | 1 (proof-of-concept) | Same routing decision + explanation trail as Python on the full `loop/PRODUCT_SCENARIOS.yaml` fixture set, byte-for-byte | Any scenario diverges and the cause isn't a deliberate, reviewed behavior change → keep Python engine authoritative |
| `classifier.py` | 2 | Routing test suite (86 cases) reproduced with identical task-type/confidence output | Any classification disagreement on existing fixtures blocks promotion |
| `hosts.py` | 3 | 100%-covered state machine; property-test every transition already covered in Python | Any transition Rust allows that Python rejects (or vice versa) |
| `usage.py` | 4 | UNKNOWN/UNSUPPORTED/AVAILABLE/EXHAUSTED/ERROR state machine, 100% coverage carried over | N/A — no live adapters registered in either language yet |
| `store.py` | 5 | Opens and round-trips an existing Python-created SQLite file (WAL mode, `busy_timeout`, `store.snapshot`) without a data migration step | Any corruption, lock contention regression, or silent snapshot data loss on the existing EPIC-018 regression fixtures |
| `refresh.py` | 6 | Catalog discovery produces the same registry diffs on recorded fixture responses (no live network calls in CI) | Async-model mismatch introduces non-determinism not present in the sync Python version |
| `diagnostics.py` | 7 | `doctor --json` output is field-identical to Python for every `Check` | Any check silently drops or reorders in a way `test_documented_commands.py`-style tests can't catch |
| `bundle.py` | 8 | All 16 credential-format fixtures from the Python redaction corpus still redact; traceback paths still survive unmasked | Any new false-positive/false-negative on the existing fixture corpus — `regex` crate vs Python `re` Unicode/lookaround differences must be resolved before promotion |
| `evaluate.py` | 9 | Bit-identical scores on the frozen 45-case holdout, run against the same fixture inputs | Any numeric drift, however small, on the frozen holdout |
| `contract.py` + `server/app.py` | 10 | `api-compatibility` CI job passes against a Rust (`axum`) server serving the same committed `contracts/http/v1/openapi.json` | Any breaking diff the existing semantic-compatibility gate would have caught |
| `plugins.py` | 11 (last, needs a fresh security review, not a mechanical port) | Full existing plugin test suite (49 cases) plus a **new** Rust-specific security review covering `std::fs` reparse-point/permission-bit semantics on Windows and Linux | Any filesystem security check that was true under Python exception hierarchies but isn't provably true under Rust's `std::fs` error kinds |
| `cli.py` | 12 (last — depends on every lower layer being ported) | `CLI_SPEC.md` contract tests pass unchanged against the `clap`-based binary | Any flag, exit code, or JSON shape divergence |
| `annotation/*` | not ported | Stays Python indefinitely as an operator tool (see foundation review §3.1) | N/A |

## Cross-cutting acceptance gates (apply to every module above)

1. The module is not considered ported until its Rust implementation passes
   the **same** test suite (or a 1:1 translated equivalent with identical
   assertions) the Python module passes today — not a newly written,
   looser suite.
2. A module may run in Rust and Python simultaneously behind a feature flag
   during its own port, but the release gates are always evaluated against
   whichever implementation is authoritative for that release — never a mix
   chosen to make a gate pass.
3. Security-sensitive modules (`plugins.py`, `bundle.py`, `store.py`) require
   an independent security review of the Rust port, not just the implementer's
   own tests.
4. No threshold in `QUALITY_GATES.yaml` may be lowered, and no mutant may be
   allowlisted, to accommodate a difference in Rust tooling output.

## Rollback

Each module is ported on its own branch, merged into the RC only after its
acceptance test passes in CI (not just locally). If a ported module fails its
acceptance test post-merge, the rollback is a revert of that module's merge
commit — the Python implementation it replaced is never deleted until the
**entire** migration (all rows above) is complete and has run green in
production for a full release cycle. This plan does not authorize deleting any
Python module until that condition is met.

## Explicitly out of scope for this plan

- No Rust code is written as part of producing this plan.
- No Python code is deleted or marked deprecated.
- No release gate, coverage threshold, or mutation threshold is changed.
- No owner-gated action (merge to `main`, tag, publish, deploy, paid
  inference) is taken.
