# TASK-149 evidence

`tests/test_observability_rust_compat.py` now compares Rust `redact_value`
against Python for nested authorization headers, provider tokens in arrays and
objects, generic API-key fields, and ordinary path/boolean values. The focused
compatibility test passes locally (**1 passed**).

Local verification: the focused compatibility case passes (**1 passed**), and
the full Python suite passes (**2,572 passed, 5 skipped in 223.97 seconds**).
Coverage is **92.030% statements** (6,905/7,503), **87.712% branches**
(1,963/2,238), and **91.038% combined** (8,868/9,741), above the required
thresholds. Rust workspace validation is recorded on TASK-148's current RC head;
the redaction probe itself compiles and runs as part of the focused differential.
Cross-platform validation for this slice is pending the RC push.

This slice only tests the existing redaction helper and adds support to its
compatibility probe. Structured logging, request-context propagation, route
spans, API-error logging, and OTel remain partial.
