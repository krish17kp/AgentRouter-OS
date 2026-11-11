# AgentRouter OS Production Completion

Updated: 2026-11-11

## Definition of done

- [ ] Every open PR reviewed, green on Linux/Windows/macOS and Python/Rust where applicable, and merged into the release candidate. PRs #30–#33 are merged through RC `019233a`; PR #33 checks passed on Linux, Windows, macOS, Python 3.10–3.13, Rust, security, and mutation jobs. PR #16 is the sole open PR and its unchanged context-band release gate has failed again; finish collecting the remaining matrix checks, then keep main promotion blocked until human evaluation meets the existing threshold.
- [ ] Python-to-Rust migration covers every public Python module with contract parity; no shipped TODO or `unimplemented!()` remains.
- [ ] The full 77-module inventory is now tracked in [`docs/RUST_PARITY_MATRIX.md`](docs/RUST_PARITY_MATRIX.md); current gaps are explicit, and only modules with differential tests are marked parity.
- [x] Full Python suite: 1,745 passed, 6 skipped; 91.15% line (6,532/7,166), 85.61% branch (1,803/2,106), and 89.89% combined coverage on Linux/Python 3.12.15. The unchanged 90%/85% quality thresholds pass; exact evidence is in `docs/COVERAGE_REPORT_2026-11-11.md`.
- [x] Routing benchmark suite runs: 12/12 gold scenarios and 15 focused tests pass; dated results document records scope and limitations; the Rust release benchmark now runs the same 10/100/1,000 candidate fleets, with a paired local p50 ratio of 2.70×–3.25× under stated synthetic conditions.
- [x] Changelog, coverage evidence, and local latency measurements are committed to the release candidate. Candidate package version is now `0.5.0rc1`, with draft release notes in `docs/RELEASE_NOTES_v0.5.0rc1.md`; final `0.5.0` packaging and publication remain blocked on parity and all release gates.
- [ ] Release candidate promoted to `main` with a tagged release.

## Completed / in progress

- [x] PR #33 reviewed and merged into RC `019233a`: Rust context-band feature extraction, validated artifact loading, stable softmax inference, and 15 prompt-level Python/Rust differential cases. All cross-platform CI checks passed; the learned model remains disabled in default routing.
- [ ] Rust doctor probe is locally validated on top of RC `07eb511`: stable JSON/text reports, safe checks for data, database, registry, generated catalogs, hosts, auth, runtime, and observability; an allowlisted redacted bundle with opt-in SQLite snapshot; environment values withheld; nine Rust CLI probe cases and focused Python compatibility tests pass. Its cross-platform CI passed on Linux, Windows, and macOS; promotion gate remains held by the frozen context-band evaluation. This is a partial R4 slice, not full CLI parity.
- [ ] Rust quota-aware reranking is wired to `route_cli --verify-live`; eight Rust unit tests and ten Python/Rust differential cases cover unsupported/available/error preservation, verified exhaustion, no recommendation, invalid states, Python-compatible Unicode sanitation, and the CLI contract. Production live adapters remain disabled. Full suite is green locally; fresh CI is pending.
- [ ] Rust doctor quota checks now share `agentrouter-hosts::detect_host`, provider mapping, and the bounded usage state machine; nine diagnostic compatibility tests pass. The full Python suite remains green at 1,720 passed/6 skipped. Overall doctor parity remains partial, and fresh CI is pending.
- [x] `agentrouter/learning.py` now has a dedicated `agentrouter-learning` Rust crate; nine differential fixtures cover caps, sample thresholds, nullable ratings, exact explanations, and ties-to-even rounding. Route CLI learning-on/off parity remains covered.
- [ ] `agentrouter/evaluation/metrics.py` and `evaluation/sampling.py` have Rust counterparts with Python differential tests. `evaluation/schema.py`, `evaluation/provenance.py`, and `evaluation/grading.py` are partial. Grading has classification-only scorecard parity; evaluator execution and `measure_all` remain Python-only. Safety, feedback-storage, report, and comparison file generation have Python/Rust differential parity. Provider and routing evaluators score supplied model records; default seed loading/custom classifier injection remain Python-only. The platform scorer accepts supplied command/group manifests; runtime Typer discovery remains Python-only. Performance timing/scoring runs in Rust with supplied models/tasks; packaged seed loading and injected classifier behavior remain Python-only. These slices need cross-platform CI. `evaluation/registry.py` mirrors descriptors and profiles but does not construct adapters. Dataset adapters, evaluation CLI, and runners remain unported. Changes after `9be78ab` need cross-platform CI.

- [x] PR #22 MCP dependency bound merged to release candidate.
- [x] PR #25 staged Rust migration, registry and provider-status probes merged to release candidate as `99f5b76`; Python remains the shipping authority.
- [x] PR #20 `prepare --all` test made offline-safe; local focused tests pass.
- [x] PR #20 pytest constrained below 9 for compatibility with pinned `mutmut==3.6.0`; merged after current-RC CI and mutation checks passed.
- [x] PR #26 reviewed and closed as superseded; its legacy registry-print binary no longer compiled against the evolved registry API.
- [x] PR #27 website, #28 macOS CI, and #29 routing benchmark/coverage evidence merged to RC (`3fcfd05`). PR #21 was closed as redundant after confirming the RC already contains its hook interpreter change.
- [x] PR #13 plugin hardening merged into the release candidate at `9958dd8` after every check passed. The mutation campaign passed: 0.9693 overall, 0.9663 safety/policy/execution, 0.9815 routing, zero unreviewed survivors; portable coverage fixes also passed Linux, Windows, macOS and supported Python CI.
- [ ] PR #16 remains blocked by context-band accuracy 0.6667 < 0.90; no gate or label policy was changed.
- [x] macOS CI is merged for Python 3.12 and Rust workspace/parity; all checks on PR #28 passed.
- [ ] Rust R4 full CLI parity and race-safe SQLite initialization. The new `doctor_cli` probe does not yet replace the shipped Python doctor; its bundle contract remains partial.
- [ ] Rust dashboard renderer/loopback server and Rust/Python feedback-stat parity merged via PR #30 at `bd98b6b`; the command remains a migration probe until the unified Rust CLI lands.
- [ ] Rust observability redaction/safe-echo helpers and bounded `ureq`/rustls OpenAI Responses transport merged via PR #30; structured logging, request context, traceback handling, and OTel integration remain unported. Live credentials, CLI wiring, and Python/Rust end-to-end parity remain open.
- [ ] Rust R5-R13 milestones and cross-platform parity. PR #30 added a bounded OpenAI Responses HTTPS transport; integration into the guarded execution command remains outstanding.
- [x] PR #31 ported Rust `agentrouter-cli::harness` with eight Python/Rust cases, cross-platform CI, and dependency hardening; merged at `a246cf6`.
- [x] PR #33 ports Rust context-band model features, artifact validation, and inference; 15 prompts (30 feature/prediction checks) plus artifact-sync test passed locally and on cross-platform CI. It remains disconnected from the default rule classifier until evaluation approves enabling learned routing.
- [x] PR #31 upgraded bundled SQLite to 3.54.1, replaced `unsafe-libyaml`, and raised the Rust minimum to 1.89; workspace tests, Clippy, security audit, and cross-platform CI passed before merge at `a246cf6`.
- [x] Website product-truth fixes, font hierarchy/motion redesign, unused shadcn CLI removal, server limits/API tests, and website lint/build CI merged via PR #27. npm build/lint and production dependency audit passed; full npm audit still reports moderate dev-tool advisories.
- [x] Benchmark evidence merged via PR #29: 12/12 routing gold scenarios and 15 focused tests; live latency/cost are explicitly not claimed.
- [ ] Full Rust parity is not complete: R4 public CLI and race-safe SQLite work remains; HTTP/MCP, provider execution, plugins/skills, evaluation/annotation, and R5-R13 remain.

## Needs Krish

- Human evaluation: arrange two independent annotators to label all 63 blinded TASK-012 cases separately; provide their JSONL outputs, then have an adjudicator resolve only disagreements and return the adjudications JSON. Run the documented dataset build/compare workflow; do not label or adjudicate with AI and do not tune against the frozen holdout.
- OpenAI live validation: provide an API key through the documented secret/environment setup and authorize one bounded paid smoke test. No secret should be committed.
- Production release/deployment: provide hosting/domain/store credentials and approve paid infrastructure/deployment after the local release gates pass; no production deployment has been run.

Latest local release checks on 2026-11-11: full Python suite, coverage,
Ruff/format, Rust workspace tests/format/Clippy, Bandit, pip-audit,
cargo-audit, wheel/sdist build, and clean-wheel install/CLI/bundle smoke pass.
The seven-gate evaluation reports six pass and context-band fail. The
diagnostic-bundle commit `07eb511` passed Linux/Windows/macOS Python/Rust,
security scan, mutation, package and API compatibility checks; only the
promotion-only evaluation gate failed. On `a4d2f79`, cross-platform Rust,
Python, security, mutation, site, and API jobs passed; the only failed job is
the unchanged frozen context-band gate (0.6667 < 0.90). The evaluation-metrics,
report-renderer, and platform-scoring Rust slices are committed locally and need
cross-platform CI. The report-writer Windows failure was CRLF translation in
Python's `Path.write_text`; Python now writes canonical LF explicitly. The
full local Python regression passes: 1,745 passed, 6 skipped; 91.15% line,
85.61% branch, and 89.89% combined coverage. Rust workspace tests pass;
Clippy, Rust format, Ruff, and Python formatting pass on the current slice.

PR #16 was reviewed against its release contract and code standards: no
separate implementation defect was identified in the reviewed diff, but the
PR is not releasable. Its immutable context-band accuracy is 0.6667 against the
unchanged 0.90 threshold; required independent human annotation is still open.
