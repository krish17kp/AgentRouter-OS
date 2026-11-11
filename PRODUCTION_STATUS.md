# AgentRouter OS Production Completion

Updated: 2026-11-11

## Definition of done

- [ ] Every open PR reviewed, green on Linux/Windows/macOS and Python/Rust where applicable, and merged into the release candidate.
- [ ] Python-to-Rust migration covers every public Python module with contract parity; no shipped TODO or `unimplemented!()` remains.
- [x] Full Python suite: 1,408 passed, 3 skipped; 87.56% line coverage and 82.08% branch coverage (Linux/Python 3.12).
- [x] Routing benchmark suite runs: 12/12 gold scenarios and 15 focused tests pass; dated results document records scope and limitations.
- [ ] Changelog updated and coverage report committed; release version bump/release notes remain pending final parity and all release gates.
- [ ] Release candidate promoted to `main` with a tagged release.

## Completed / in progress

- [x] PR #22 MCP dependency bound merged to release candidate.
- [x] PR #25 staged Rust migration, registry and provider-status probes merged to release candidate as `99f5b76`; Python remains the shipping authority.
- [x] PR #20 `prepare --all` test made offline-safe; local focused tests pass.
- [x] PR #20 pytest constrained below 9 for compatibility with pinned `mutmut==3.6.0`; merged after current-RC CI and mutation checks passed.
- [x] PR #26 reviewed and closed as superseded; its legacy registry-print binary no longer compiled against the evolved registry API.
- [ ] PRs #13, #16, #21, #27 need final disposition against the latest RC; PR #13 mutation gate currently fails.
- [ ] macOS CI added for Python 3.12 full tests and the Rust workspace/parity matrix; awaits checks.
- [ ] Rust R4 full CLI parity and race-safe SQLite initialization.
- [ ] Rust R5-R13 milestones and cross-platform parity.
- [x] PR #27 website product-truth fixes, unused shadcn CLI removal, and site CI added; npm build/lint and production dependency audit pass. Full npm audit still reports moderate dev-tool advisories.

## Needs Krish

- Human evaluation: arrange two independent annotators plus an adjudicator for the prepared TASK-012 blinded packs. Return completed annotation files and adjudication output; AI-generated labels cannot substitute.
- OpenAI live validation: provide an API key through the documented secret/environment setup and authorize a bounded paid smoke test. No secret should be committed.
- Production release credentials/ownership: supply required hosting/domain/store credentials and approve any paid infrastructure or production deployment once local release gates pass.
