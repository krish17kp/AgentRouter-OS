# Independent audit — TASK-006

## verification-engineer — all 5 criteria PASS
- typecheck clean; npm test 7/7 (now 8/8 after repair); python suite 426 (untouched).
- Method-by-method parity table vs sdk.py + FastAPI route table: all 9 endpoints match
  (method+path); body-cleaning parity (drop undefined/null, keep false/0; route always
  sends no_log:false); error contract; X-API-Key; trailing-slash strip.
- Tests judged meaningful (mock fetch asserts method/url/body/headers), not vacuous.

## Divergence found (fixed in repair)
- Non-JSON error body (e.g. proxy/gateway 502 HTML) crashed the TS client with an uncaught
  SyntaxError (JSON.parse before the error path), whereas the Python SDK guards with
  try/except ValueError. Real parity bug.

## Non-issues noted
- timeout exception types differ (AbortError vs httpx.TimeoutException) — both propagate
  unwrapped on both sides; consistent with contract, untested on both.
- Python close()/context-manager has no TS equivalent — TS uses stateless global fetch.
