# Repair loop — TASK-001

Iteration 0 (from independent audit LOW notes, no functional defects found):
1. contextvar stale-id risk (security LOW #2)
   - classify: hardening (not a defect today; single caller path safe)
   - root cause: request-id contextvar set but never cleared after the response
   - fix: `try/finally: set_request_id(None)` in server/app.py middleware
   - regression: covered by existing test_server_route_logs_with_request_id + concurrency check
2. generic route_span attribute leak risk (security LOW #1)
   - fix: docstring contract "metadata only, never task/prompt text"
Re-verify: `pytest -q` -> 380 passed; ruff clean. No further iterations needed.
