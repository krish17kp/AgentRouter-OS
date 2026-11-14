# Plan — TASK-006 TypeScript SDK (L3)

## Contract source
agentrouter/sdk.py (AgentRouterClient, 121 lines). Mirror exactly: methods, HTTP
method+path, error shape ({error:{code,message}} -> AgentRouterError), _clean semantics
(drop undefined/null; keep false/0).

## Design (ponytail, zero runtime deps)
- sdk/typescript/src/index.ts: AgentRouterClient (global fetch), AgentRouterError, types.
- Node >= 22: global fetch + native TS type-stripping -> no build step, no ts-node/tsx.
- Injectable fetchImpl for testing (no server needed).
- Dev-only deps: typescript (typecheck) + @types/node.

## Verify
tsc --noEmit (typecheck); node --experimental-strip-types --test (mock-fetch contract
tests). Python suite untouched.

## Risk: low (new isolated package; no Python change).
