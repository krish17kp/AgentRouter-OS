# TASK-150 evidence

The focused API schema differential suite passes **57 tests**. It checks Rust
and Python for context-window values beyond both signed and unsigned 64-bit
ranges, a 30-digit integer string, boolean coercion, and rejection of fractional,
exponent-string, null, and non-scalar inputs.

`cargo test -p agentrouter-api` passes all **3 unit tests**; the full Rust
workspace test suite and workspace Clippy pass. Full Python regression passes **2,580 tests, 5
skipped, 0 failed** in 237.14 seconds. Coverage is **92.030% statements**
(6,905/7,503), **87.712% branches** (1,963/2,238), and **91.038% combined**
(8,868/9,741), above release thresholds. See
[`docs/COVERAGE_REPORT_2026-11-14-TASK-150.md`](../../../docs/COVERAGE_REPORT_2026-11-14-TASK-150.md).

Cross-platform validation is pending the RC push. The response schema module
remains Partial for complete public-model and FastAPI compatibility.
