# TASK-013 progress

Branch: `task/TASK-013-catalog-provenance` (from `release/agentrouter-v0.5-rc1`).
Status: **freshness/status + rollback delivered** (additive, no refresh-format
change). Provenance-block + deprecation reconciliation deferred to a follow-up to
keep this increment low-risk and independently verifiable.

## Delivered (this increment)

- `agentrouter/catalog_ops.py` (offline, read-only except rollback):
  - `read_status` / `list_generated` — freshness of each
    `models.<provider>.generated.yaml`, derived from the newest entry
    `last_updated` and judged against `registry.STALE_AFTER_DAYS` (single source
    of truth; no format change to generated files).
  - `rollback` — back up (`.bak`) then remove one generated file; the manual
    `models.yaml` is never touched, so routing reverts cleanly.
- CLI: `agentrouter providers status` (per-catalog age + fresh/stale; offline) and
  `agentrouter providers rollback <provider>` (safe, reversible revert).
- `tests/test_catalog_ops.py` — 9 tests (fresh/stale/no-date, newest-wins, sorted
  listing, rollback backup+remove+idempotent, and the three CLI paths).

## Guardrails honoured

- No routing/threshold/gate change; manual-wins semantics unchanged; frozen
  holdout untouched. `catalog_ops` is a leaf (imports only `registry.STALE_AFTER_DAYS`).

## Deferred (still in TASK-013 scope, follow-up)

- Structured file-level `provenance` block in `write_generated_registry`
  (source_url, fetched_at UTC, count, tool_version) — needs a loader-tolerance
  check first so the extra top-level key never breaks `load_all_models`.
- Deprecation reconciliation: report models in the generated file but absent from
  the live catalog on refresh (report-only; never auto-delete).
