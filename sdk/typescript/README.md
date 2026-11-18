# @agentrouter/sdk (TypeScript)

Typed client for the local AgentRouter OS REST API — contract parity with the
Python SDK (`agentrouter/sdk.py`).

```ts
import { AgentRouterClient, AgentRouterError } from "@agentrouter/sdk";

const client = new AgentRouterClient("http://127.0.0.1:8000", { apiKey: process.env.AGENTROUTER_API_KEY });

const decision = await client.route("summarize this PR");
console.log(decision.recommendation, decision.decision_id);

try {
  await client.getDecision("d_missing");
} catch (e) {
  if (e instanceof AgentRouterError) console.error(e.status, e.code);
}
```

## Methods
`health`, `ready`, `models`, `hosts`, `classify`, `route`, `getDecision`,
`feedback`, `executeDryRun` — mirroring the Python SDK. Non-2xx responses raise
`AgentRouterError` (`.status`, `.code`). Optional fields set to `undefined` are
omitted from the request body; explicit `false`/`0` are kept.

## Requirements
Node >= 22 (uses global `fetch` and native TypeScript type-stripping).

```bash
npm install       # dev deps (typescript, @types/node)
npm run typecheck # tsc --noEmit
npm test          # node:test contract tests (mock fetch, no server needed)
```

No runtime dependencies; ships as source (`src/index.ts`).
