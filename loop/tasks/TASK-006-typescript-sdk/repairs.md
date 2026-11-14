# Repair loop — TASK-006

1. Parity bug (self-caught by tests): route() must always send no_log:false. Fixed
   `no_log: opts.noLog ?? false`. Also fixed npm test script to `test/*.test.ts` (directory
   form dropped --experimental-strip-types into subprocesses -> MODULE_NOT_FOUND).
2. Divergence (verification): non-JSON error body -> SyntaxError instead of AgentRouterError.
   Fixed: wrap JSON.parse in try/catch -> {} (mirrors Python's except ValueError).
   Regression test: 502 text/plain body -> AgentRouterError(status=502, code=error, msg~text).
Re-verify: typecheck clean; 8/8 tests pass; python 426.
