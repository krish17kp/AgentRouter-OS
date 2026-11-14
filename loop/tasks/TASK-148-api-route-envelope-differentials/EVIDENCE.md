# TASK-148 evidence

The focused route-service differential selection passes **3 tests**: the
existing route preview and new high-risk and explicit-quality-preference cases.
Both new scenarios compare the complete Rust service response against
`agentrouter.server.service.route_task()` using the initialized temporary home.
The full Linux/Python 3.12 suite passes **2,572 tests, 5 skipped** in 239.27
seconds. Statement, branch, and combined coverage is 92.030%, 87.712%, and
91.038%, respectively, in
[`docs/COVERAGE_REPORT_2026-11-14-TASK-148.md`](../../../docs/COVERAGE_REPORT_2026-11-14-TASK-148.md).

No product implementation, frozen dataset, or release threshold changed. The
module remains Partial pending logging/span, FastAPI lifecycle, and middleware
parity. Hosted validation for this slice is pending.
