# TASK-197 — Fail-closed execution planning

## Objective

Add a Rust-native planning boundary for routed execution without enabling a
process, provider call, credential read, or remote request.

## Acceptance

- policy defaults disable remote execution, approval, and unavailable hosts;
- high-risk and human-approval-required classifications fail closed;
- API routes remain disabled without an explicit remote policy and adapter;
- manual routes produce an operator-handoff plan;
- successful plans always expose `execution_enabled: false`.
