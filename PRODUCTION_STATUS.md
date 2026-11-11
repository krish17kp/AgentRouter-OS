# AgentRouter OS Production Completion

Updated: 2026-11-11

## Definition of done

- [ ] Every open PR reviewed, green on Linux/Windows/macOS and Python/Rust where applicable, and merged into the release candidate.
- [ ] Python-to-Rust migration covers every public Python module with contract parity; no shipped TODO or `unimplemented!()` remains.
- [x] Routing benchmark suite runs: 12/12 gold scenarios and 15 focused tests pass; dated results document records scope and limitations.
- [ ] Changelog, version bump, release notes, full tests, and coverage report are committed.
- [ ] Release candidate promoted to `main` with a tagged release.

## Completed / in progress

- [x] PR #22 MCP dependency bound merged to release candidate.
- [x] PR #25 staged Rust migration, registry and provider-status probes merged to release candidate as `99f5b76`; Python remains the shipping authority.
- [x] PR #20 `prepare --all` test made offline-safe; local focused tests pass.
- [x] PR #20 pytest constrained below 9 to match pinned `mutmut==3.6.0` API; current CI exposed baseline CLI and staleness test failures that are being diagnosed.
- [ ] PR #20 mutation gate rerun on new commit `839a0c4`; Python matrix currently fails and needs repair against current RC.
- [ ] PRs #13, #16, #21, #26, #27 reviewed against latest release candidate and disposition recorded.
- [ ] Rust R4 full CLI parity and race-safe SQLite initialization.
- [ ] Rust R5-R13 milestones and cross-platform parity.
- [ ] PR #27 website product-truth fixes, security/dependency cleanup, and website CI.

## Needs Krish

- Human evaluation: arrange two independent annotators plus an adjudicator for the prepared TASK-012 blinded packs. Return completed annotation files and adjudication output; AI-generated labels cannot substitute.
- OpenAI live validation: provide an API key through the documented secret/environment setup and authorize a bounded paid smoke test. No secret should be committed.
- Production release credentials/ownership: supply required hosting/domain/store credentials and approve any paid infrastructure or production deployment once local release gates pass.
