# Test-first contract — TASK-006

sdk/typescript/test/client.test.ts (node:test, mock fetch):
- route POSTs /v1/route with cleaned body; KEEPS no_log:false (parity), drops undefined.
- classify drops undefined opts.
- non-2xx -> AgentRouterError with status + code.
- apiKey -> X-API-Key header.
- base url trailing slash stripped.
- getDecision GET url-encoded id.
- feedback body (decision_id+rating, note dropped when undefined).

Gates: `npm run typecheck` clean; `npm test` all pass; python `pytest -q` still 426.
