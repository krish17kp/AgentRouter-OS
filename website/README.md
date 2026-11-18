# Agent Router OS — Buildathon website

Standalone React + TypeScript + Vite presentation site for Agent Router OS.

## Run locally

```sh
npm ci
npm run dev
npm run build
```

## Product-truth boundaries

- The playground is a **recorded CLI demonstration**. Its three fixtures were refreshed from
  `agentrouter route ... --json --no-log` on the website branch.
- By default the playground is a recorded CLI demonstration and never sends visitor prompts.
  To opt into a local live route, start AgentRouter's local API and build/run the website with
  `VITE_AGENTROUTER_API_URL=http://127.0.0.1:8000` plus
  `AGENTROUTER_CORS_ORIGINS=http://localhost:5173` on the API process. Live browser requests
  always include `no_log: true`, never carry an API key, and the UI labels the source as
  **local API**. A public static build should leave `VITE_AGENTROUTER_API_URL` unset.
- No model execution, credential, local database, private host state, or unrestricted API is
  exposed. The current shipping router remains local-first.
- Rust migration content is limited to verified R1 workspace/core-type completion; later
  milestones remain planned or blocked in line with `RUST_MIGRATION_PLAN.md`.

## Design notes

GSAP is the main motion system; Lenis uses GSAP's single ticker and cleans it up on unmount.
Vanta NET and Three.js are dynamically imported on non-reduced-motion desktop sessions. The CSS
grid and glow background remains the static fallback when WebGL is unavailable.

## Deployment

The output is `dist/` after `npm run build`, suitable for static hosting. Configure the host to
serve `index.html` for client navigation and do **not** add a routing backend or environment
secrets. A public deployment needs the owner's approved hosting destination/connection; none is
configured in this checkout.
