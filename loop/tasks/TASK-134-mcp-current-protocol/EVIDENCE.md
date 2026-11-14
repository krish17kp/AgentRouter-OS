# TASK-134 evidence

## Verification

- Focused MCP, Rust protocol, and unified CLI suite: **23 passed** on
  Python 3.10/MCP 1.30.0, Python 3.11/MCP 2.3.0, and Python 3.12/MCP 2.3.0.
- Full Python regression on Linux/Python 3.12.15, pytest 9.0.3, MCP 2.3.0:
  **2,525 passed, 5 skipped, 0 failed** in 317.45 seconds.
- Coverage: **91.971% statements** (6,896/7,498), **87.690% branches**
  (1,959/2,234), and **90.988% weighted combined** (8,855/9,732).
- `agentrouter/mcp_server.py` has 100% statement and branch coverage.
- Full Rust workspace tests, strict Clippy, Rust formatting, Ruff, and diff
  checks pass; the MCP crate has 6 passing unit tests.
- Python sdist and wheel builds succeed. Wheel metadata carries the intended
  Python 3.10/MCP 1.x and Python 3.11+/MCP 2.x dependency markers.
- The Rust CI workflow YAML parses and now runs dedicated MCP tests on Python
  3.10 and 3.11. Hosted checks for this task's push are pending.

Protocol behavior follows the official MCP 2026-07-28 stateless/versioning
specification and Python SDK v2 migration/release guidance; source links are in
`docs/RUST_MCP_SERVER.md`. The frozen context-band gate remains unchanged at
0.6667 < 0.90.
