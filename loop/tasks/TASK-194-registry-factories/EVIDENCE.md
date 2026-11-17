# TASK-194 evidence

Date: 2026-11-17

Added `registry_api::available_adapter_factories`, returning ordered callable
factories that construct the concrete `DatasetAdapter` facade. The focused
registry test constructs all eight registered adapters and checks their names;
the existing real-loader blocker remains unchanged.

```console
cargo test --locked -p agentrouter-evaluation registry_api::tests -- --nocapture
# 3 passed
```
