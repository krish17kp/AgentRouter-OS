# TASK-205 — Current optimized release smoke

## Objective

Revalidate the latest release binary after execution and orchestration changes
with Python absent and release-only host discovery.

## Acceptance

- release build and advisory scan complete;
- isolated init/route/plan/doctor/MCP smoke runs with no Python environment;
- unavailable execution hosts fail closed by default and are previewable only
  with the explicit include-unavailable flag;
- evidence records the remaining unmaintained dependency warning honestly.
