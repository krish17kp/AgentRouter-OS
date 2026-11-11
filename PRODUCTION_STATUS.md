# AgentRouter OS Production Completion

Updated: 2026-11-11

## Definition of done

- [ ] Every open PR reviewed, green on Linux/Windows/macOS and Python/Rust where applicable, and merged into the release candidate. PRs #27–#33 are merged; PR #16 is the sole open PR and remains blocked by the frozen context-band gate (0.6667 < 0.90). TASK-029 through TASK-037 hosted Rust/Python checks pass across Linux/Windows/macOS; security, site, and mutation checks pass. The latest general CI fails only at the unchanged promotion gate; live smoke is skipped without credentials.
- [ ] Python-to-Rust migration covers every public Python module with contract parity; no shipped TODO or `unimplemented!()` remains.
- [ ] The full 77-module inventory is tracked in [`docs/RUST_PARITY_MATRIX.md`](docs/RUST_PARITY_MATRIX.md); current gaps are explicit, and only modules with full-module differential tests are marked parity (35 modules meet that bar after TASK-051).
- [x] Full Python suite: 1,893 passed, 6 skipped; 92.16% line (6,604/7,166), 87.27% branch (1,838/2,106), and 91.05% combined coverage on Linux/Python 3.12.15. The unchanged 90%/85% quality thresholds pass; exact evidence is in `docs/COVERAGE_REPORT_2026-11-11.md`.
- [x] Routing benchmark suite runs: 12/12 gold scenarios and 15 focused tests pass; dated results document records scope and limitations; the Rust release benchmark now runs the same 10/100/1,000 candidate fleets, with a paired local p50 ratio of 2.70×–3.25× under stated synthetic conditions.
- [x] Changelog, coverage evidence, and local latency measurements are committed to the release candidate. Candidate package version is now `0.5.0rc1`, with draft release notes in `docs/RELEASE_NOTES_v0.5.0rc1.md`; final `0.5.0` packaging and publication remain blocked on parity and all release gates.
- [ ] Release candidate promoted to `main` with a tagged release.

## Completed / in progress

- [x] PR #33 reviewed and merged into RC `019233a`: Rust context-band feature extraction, validated artifact loading, stable softmax inference, and 15 prompt-level Python/Rust differential cases. All cross-platform CI checks passed; the learned model remains disabled in default routing.
- [ ] Rust doctor probe is locally validated on top of RC `07eb511`: stable JSON/text reports, safe checks for data, database, registry, generated catalogs, hosts, auth, runtime, and observability; an allowlisted redacted bundle with opt-in SQLite snapshot; environment values withheld; nine Rust CLI probe cases and focused Python compatibility tests pass. Its cross-platform CI passed on Linux, Windows, and macOS; promotion gate remains held by the frozen context-band evaluation. This is a partial R4 slice, not full CLI parity.
- [x] Rust quota-aware reranking is wired to `route_cli --verify-live`; eight Rust unit tests and ten Python/Rust differential cases cover unsupported/available/error preservation, verified exhaustion, no recommendation, invalid states, Python-compatible Unicode sanitation, and the CLI contract. PR #16's cross-platform CI passed for the RC base; production live adapters remain disabled.
- [x] Rust doctor quota checks share `agentrouter-hosts::detect_host`, provider mapping, and the bounded usage state machine; nine diagnostic compatibility tests pass. Full local regression passes; overall doctor parity remains partial.
- [x] `agentrouter/learning.py` now has a dedicated `agentrouter-learning` Rust crate; nine differential fixtures cover caps, sample thresholds, nullable ratings, exact explanations, and ties-to-even rounding. Route CLI learning-on/off parity remains covered.
- [x] Rust evaluation scorer/report/comparison slices passed the RC's cross-platform Rust and Python/Rust checks. The gold adapter is now full-module parity across metadata, availability, description, all 165 records, checksum, and deterministic sampling. Shared adapter base methods, external adapters, evaluation CLI/runner, and annotation remain Python-only.

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
- [x] Rust AgentRouter gold adapter matches Python metadata, availability, description, loading, checksums, and deterministic sampling; exact JSON parity covers all 165 committed cases and a Unicode/defaults fixture. Cross-platform differential CI is added in this increment.
- [x] Shared Rust fixture adapter-base methods match six external adapter fixtures for metadata, availability, describe, loading/validation, checksums, deterministic sampling, and skipped-external real mode. External downloads and dataset-specific real-data transformations remain unported.
- [x] TASK-029 ports TwinRouterBench dynamic-track skip status; its Rust and Python/Rust checks pass on Linux, Windows, and macOS.
- [x] TASK-030 completes evaluation provenance parity with a Rust environment snapshot; its cross-platform Rust and Python/Rust checks pass.
- [ ] TASK-031 completes Rust evaluation schema parity for defaults, serialization, hash/checksum methods, and invalid-input validation. Local checks pass; hosted platform compatibility is finishing.
- [x] TASK-032 ports human annotation resolution and adjudication to Rust. Seven differential cases cover agreement, abstention, unresolved conflicts, and explicit human decisions; the required independent annotator round is still under **Needs Krish**.
- [x] TASK-033 ports Python-compatible prompt normalization, near-duplicate similarity, clustering, and leakage reports. Rust/Python checks pass across Linux/Windows/macOS; Ruff formatting is corrected. The frozen holdout remains read-only.
- [x] TASK-034 ports deterministic annotation splits, cluster preservation, and fail-closed frozen-holdout leakage checks. Local and cross-platform Rust/Python tests pass.
- [ ] TASK-035 ports annotation schemas with Python-compatible datetime normalization. Fourteen focused differentials and the Rust workspace, Clippy, format, Ruff checks pass. Scalar coercion and the full `fromisoformat` edge grammar remain incomplete, so the module stays Partial; hosted Rust/Python compatibility passes all three platforms.
- [x] TASK-036 ports the optional repository-impact graph signal. TASK-041/042/043 now match Python malformed-shape behavior, its four-entry LRU cache (including cached fallbacks and eviction), and contextual Unicode lowercase. Thirteen focused differentials, full Python regression, full workspace/Clippy/format/Ruff pass locally; cross-platform CI is pending push.
- [x] TASK-037 completes Rust annotation pack behavior: CPython-seeded shuffle for arbitrary integer seeds, resume filtering, label-free progress, order-preserving merge, disagreement-only adjudication packs, and Python-compatible CSV. Eight focused cases and the full local regression pass; cross-platform hosted checks pass on `dca1300`.
- [x] TASK-038 ports annotation candidate/dataset YAML, labels JSONL, sorted manifest JSON, and canonical split SHA-256. Four focused file/hash differential tests and the full Python regression pass locally, including exact JSONL/manifest bytes and Unicode hash parity. Windows CI exposed Python CRLF translation parity; fixed in `1c88b3c`; Rust workspace and Python/Rust compatibility now pass Linux, Windows, and macOS.
- [x] TASK-039 ports deterministic annotation candidate generation from the 63-prompt bank. Fifty generation differentials plus an exact bank-inventory case cover 5 positive/negative/arbitrary-width seeds, 10 Python slice counts, exact IDs/source/templates, and prompt ordering. Full Python regression is 1,868/6; Rust workspace, Clippy, format, Ruff pass locally. Linux/Windows/macOS compatibility passes on the newline-fix recheck.
- [x] TASK-040 ports `annotation.compare`: rules/learned/hybrid reports, macro-F1, per-band recall, Python-compatible seeded bootstrap CI, ECE, abstentions, and fallback rates. Five differential cases cover exact output and threshold behavior; full Python regression is 1,868/6, and full Rust workspace/Clippy/format/Ruff pass. Rust workspace and Python/Rust compatibility pass on Linux, Windows, and macOS at `8a4286a`. The implementation does not alter the frozen release gate.
- [x] TASK-041 aligns the graph signal's valid-JSON malformed-shape behavior with Python, including Python iterable mappings/strings and raised errors for truthy scalar collections. Eleven focused graph differentials and full Python 1,875/6 passed locally; Rust workspace and compatibility checks pass Linux/Windows/macOS at `75d4690`. The cache semantics followed in TASK-042.
- [x] TASK-042 ports the graph signal's maxsize-four LRU cache, including cached unreadable/missing/invalid-JSON fallbacks and least-recently-used eviction. Twelve focused graph differentials and full Python 1,876/6 pass; hosted workspace/compatibility checks pass Linux/Windows/macOS at `7399b3b`.
- [x] TASK-043 matches Python's context-sensitive Greek final-sigma lowercase behavior in graph node/edge identifiers. Thirteen focused graph differentials, full Python 1,877/6, full Rust workspace/Clippy/format/Ruff pass locally; cross-platform CI follows push.
- [x] TASK-044 ports the complete frozen context-band evaluator: checksummed YAML loading, category validation, Python-compatible Unicode normalization and SequenceMatcher leakage checks, scoring, Wilson intervals, CPython-seeded bootstrap, historical comparator, and the frozen generalization report. Three Python/Rust differential tests compare the full release report, custom predictions/score output, sequence ratios (including autojunk behavior), and leak order; focused tests and evaluation-crate Clippy pass locally. The frozen score and release threshold were not changed.
- [x] TASK-045 ports the `agentrouter.evaluation` package facade as a Rust public module that re-exports the same three schema types; a Python/Rust contract test compares the public export list exactly.
- [x] TASK-046 ports the `agentrouter.annotation` package constants through a Rust facade; the cross-language test compares schema version, category order, and split names.
- [ ] TASK-047 adds the evaluator package facade, validated embedded seed-model loading, and the same seven exports. The seed catalog and export list have an exact local compatibility test; evaluator runtime orchestration remains partial because the underlying Rust evaluator ports still accept explicit catalogs/commands rather than discovering Python runtime state.
- [x] TASK-048 ports the top-level package version accessor by reading the canonical `pyproject.toml` metadata at Rust compile time; exact Python/Rust version parity is tested.
- [ ] TASK-049 aligns annotation confidence deserialization with Pydantic's number, numeric-string, and boolean coercions. The schema compatibility suite now includes these inputs and passes 18 focused cases; annotation schema stays Partial pending complete datetime grammar and remaining scalar coercions.
- [ ] TASK-050 aligns Pydantic boolean coercion (booleans, 0/1 numeric forms, and recognized strings) and integer coercion for manifest schema versions; annotation schema remains Partial for remaining coercion surfaces.
- [x] TASK-051 confirms the evaluation-adapters and server package initializers intentionally expose no runtime symbols; Rust package markers and a differential export test now document that no-op public contract.
- [ ] TASK-052 aligns manifest integer coercion with Python for schema version and count maps, including signed values, numeric strings, booleans, and integral floats. The annotation schema stays Partial pending string/coercion and datetime edge audits.
- [x] TASK-053 adds Rust registered dataset specs and fixture collection, with differential coverage for ordering, profiles, every fixture, deterministic sampling, availability/checksums, Massive language filtering, real-mode blockers, unknown lookups, and error text. Remote dataset loaders and real-data adapter transforms remain Partial.
- [x] TASK-054 adds an offline Rust runner for registered profiles and datasets, classification grading, dataset quality, explicit provenance, and `measure_all` across all seven dimensions. Thirteen Python/Rust differential cases cover collection reports, end-to-end profile results, multilingual filtering, all scorecard dimensions, release gates, and fail-closed real-mode behavior. Automatic runtime environment, CLI-state discovery, and real dataset downloads remain Partial.
- [x] TASK-055 tightens annotation timestamp parity: 26 focused cases now cover Python-compatible date-only, compact offset, fractional seconds, comma fractions, omitted seconds, and rejected invalid separators/date shapes. The annotation module remains Partial pending broader scalar coercion and a full accepted-input grammar audit.
- [x] PR #31 upgraded bundled SQLite to 3.54.1, replaced `unsafe-libyaml`, and raised the Rust minimum to 1.89; workspace tests, Clippy, security audit, and cross-platform CI passed before merge at `a246cf6`.
- [x] Website product-truth fixes, font hierarchy/motion redesign, unused shadcn CLI removal, server limits/API tests, and website lint/build CI merged via PR #27. npm build/lint and production dependency audit passed; full npm audit still reports moderate dev-tool advisories.
- [x] Benchmark evidence merged via PR #29: 12/12 routing gold scenarios and 15 focused tests; live latency/cost are explicitly not claimed.
- [ ] Full Rust parity is not complete: R4 public CLI and race-safe SQLite work remains; HTTP/MCP, provider execution, plugins/skills, evaluation adapter base/runner/annotation, and R5-R13 remain. The full 77-file module inventory is in [`docs/RUST_PARITY_MATRIX.md`](docs/RUST_PARITY_MATRIX.md).

## Needs Krish

- Human evaluation: arrange two independent annotators to label all 63 blinded TASK-012 cases separately; provide their JSONL outputs, then have an adjudicator resolve only disagreements and return the adjudications JSON. Run the documented dataset build/compare workflow; do not label or adjudicate with AI and do not tune against the frozen holdout.
- OpenAI live validation: provide an API key through the documented secret/environment setup and authorize one bounded paid smoke test. No secret should be committed.
- Production release/deployment: provide hosting/domain/store credentials and approve paid infrastructure/deployment after the local release gates pass; no production deployment has been run.

Latest local checks on 2026-11-11: full Python suite and coverage,
Ruff/format, Rust workspace tests/format/Clippy, Bandit, pip-audit,
cargo-audit, wheel/sdist build, and clean-wheel install/CLI/bundle smoke pass.
The seven-gate evaluation reports six pass and context-band fail. PR #16's
cross-platform Python/Rust, security, mutation, package, API, and site checks
pass; its promotion-only gate fails on context-band 0.6667 < 0.90, and live
smoke is skipped without credentials. The full local regression now passes:
1,913 passed, 6 skipped; 92.34% line, 87.37% branch, and 91.21% combined
coverage. The Rust workspace tests, workspace Clippy, Rust formatting, Ruff,
and Python formatting pass at `03baa84`. CI at `03baa84` is in progress; the
website job is green. PR #16 remains promotion-blocked by the unchanged frozen
context-band result and the human annotation requirement.

PR #16 was reviewed against its release contract and code standards: no
separate implementation defect was identified in the reviewed diff, but the
PR is not releasable. Its immutable context-band accuracy is 0.6667 against the
unchanged 0.90 threshold; required independent human annotation is still open.
