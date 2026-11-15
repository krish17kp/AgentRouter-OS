# TASK-152 evidence

Focused Python/Rust observability, correlation, and HTTP compatibility pass **85 tests, 1
skipped**. The shared Rust crate passes five unit tests. Direct differentials
cover route metadata and redaction; HTTP checks cover both enabled and disabled
logging, real response metadata, and SHA-256 request correlation.

Independent audit found and verified repairs for credential URLs, opaque values
shaped like source paths, nested secret-shaped keys, non-JSON metadata values,
and a caller-provided request-id override. Non-string map keys are converted
and redacted before JSON serialization. Python and Rust now strictly redact
structured logs while preserving human-readable paths in diagnostic redaction.
The reviewer found no remaining release-blocking issue in this slice.

Full Python regression passes **2,590 tests, 5 skipped** in 387.16 seconds;
coverage is **92.052% statements**, **87.756% branches**, and **91.064%
combined**. The Rust workspace, strict Clippy, format, Ruff, wheel/sdist build,
and clean-wheel CLI/API/MCP/plugin smoke pass. See
[`docs/COVERAGE_REPORT_2026-11-15-TASK-152.md`](../../../docs/COVERAGE_REPORT_2026-11-15-TASK-152.md).
Hosted Linux/Windows/macOS validation awaits the RC push. The observability module
remains Partial for spans, optional OTel, and full API-error record parity.
