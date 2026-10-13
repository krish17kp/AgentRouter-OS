# TASK-009 independent audit

The first independent review found that CI still used the legacy evaluator, failed
gates could exit zero, the historical comparator imported mutable live helpers,
provenance omitted dirty-tree/code identity, and durable dashboards contradicted the
new score. Repairs added:

- canonical `eval run --all` CI wiring and strict `--require-release-ready` mode;
- strict release-workflow enforcement;
- immutable historical constants and pinned historical metric regression tests;
- command-level full-path tests without hardcoding a permanent product failure;
- git dirty state and classifier SHA-256 provenance;
- a separate held-out failure CSV and unambiguous in-sample report label;
- explicit legacy gold-set readiness scope.

The canonical artifacts and durable state were regenerated/refreshed on 2026-07-20.
Final independent audit re-run is pending.
