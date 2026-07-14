# AgentRouter OS — Local REST API (Phase P7)

A local, offline-safe HTTP surface over the same classifier + routing engine the
CLI uses. It classifies tasks, recommends a model/host, logs decisions, records
feedback, and previews execution plans. **It never runs a task** — see the
[no-remote-execution guarantee](#no-remote-execution-guarantee).

## Running

```bash
pip install "agentrouter-os[server]"
uvicorn agentrouter.server.app:app            # http://127.0.0.1:8000
uvicorn agentrouter.server.app:app --reload   # dev auto-reload
```

The app reads its registry/decision store from `AGENTROUTER_HOME`
(default `~/.agentrouter`). Run `agentrouter init` once to seed it.

- Interactive docs: `GET /docs` (Swagger UI)
- OpenAPI schema: `GET /openapi.json`

Both are generated automatically by FastAPI.

## Authentication

Local mode by default (open). If the environment variable `AGENTROUTER_API_KEY`
is set, every `/v1/*` endpoint requires a matching `X-API-Key` header; a missing
or wrong key returns `401`. `/health` and `/ready` are always open (liveness
probes).

```bash
export AGENTROUTER_API_KEY=your-secret
curl -H "X-API-Key: your-secret" http://127.0.0.1:8000/v1/models
```

## Request ID

Every response carries an `X-Request-ID` header. If the client sends one it is
echoed back; otherwise the server generates a UUID. Use it to correlate logs.

## Error format

Non-2xx responses use a structured envelope:

```json
{ "error": { "code": "not_found", "message": "no decision 'd_99999'" } }
```

Codes: `unauthorized` (401), `not_found` (404), `validation_error` (422),
`unavailable` (503), `error` (other).

## Endpoints

Contract is versioned under `/v1`. `/health` and `/ready` are unversioned probes.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | `/health` | open | Liveness. `{"status":"ok"}` |
| GET  | `/ready` | open | Registry loads? `200 {"status":"ready"}` or `503` |
| GET  | `/v1/models` | key | Catalog: vendor, model_id, release channel, context window, best host availability |
| GET  | `/v1/hosts` | key | Availability of every known execution host (read-only) |
| POST | `/v1/classify` | key | Classify a task → classification JSON |
| POST | `/v1/route` | key | Classify + route → recommendation, fallback, execution_route; persists a decision |
| GET  | `/v1/decisions/{id}` | key | Stored decision or `404` |
| POST | `/v1/feedback` | key | Record a rating for a decision |
| POST | `/v1/execute/dry-run` | key | Return the execution plan; runs nothing |

### GET /v1/models

```json
[{ "vendor": "anthropic", "model_id": "claude-sonnet-5", "key": "anthropic/claude-sonnet-5",
   "release_channel": "stable", "context_window": 200000, "host_availability": "available" }]
```

### GET /v1/hosts

```json
[{ "host": "claude-code", "availability": "unavailable", "reason": "'claude' not found on PATH" },
 { "host": "manual", "availability": "available", "reason": "manual execution is always available" }]
```

### POST /v1/classify

Body:

```json
{ "task": "summarize this PDF", "context_tokens": 4000, "risk": "low", "tools": ["file"] }
```

`context_tokens`, `risk` (`low|medium|high`) and `tools` are optional overrides.
Returns the full classification (task_type, complexity, risk, context_band,
tool_needs, approval_level, confidence, needs_clarification, ...).

### POST /v1/route

Body:

```json
{ "task": "refactor the auth module", "prefer": "quality",
  "context_tokens": null, "risk": null, "tools": null, "no_log": false }
```

Returns `decision_id`, `task`, `classification`, `weights`, `weight_shifts`,
`excluded`, `scores`, `recommendation`, `fallback`, `gates`, `prompt`,
`execution_route`, `fallback_execution_route`. The decision is persisted (and a
`decision_id` returned) unless `no_log` is `true`, in which case `decision_id`
is `null`.

### GET /v1/decisions/{id}

Returns the stored decision payload (as logged by `/v1/route` or the CLI), or
`404`.

### POST /v1/feedback

Body: `{ "decision_id": "d_00001", "rating": 5, "note": "great pick" }`
(`rating` is 1–5). Returns `{ "decision_id": ..., "recorded": true }`, or `404`
if the decision does not exist. Feedback is written to the existing `feedback`
table in `agentrouter.db`, so it feeds `agentrouter stats`.

### POST /v1/execute/dry-run

Body: `{ "decision_id": "d_00001" }`. Returns the *plan only*:

```json
{ "decision_id": "d_00001", "would_execute": false, "auto_execute_allowed": false,
  "recommendation": {...}, "execution_route": {...},
  "argv": ["claude", "-p", "{prompt}"],
  "note": "dry-run only: no process was or will be spawned by this endpoint" }
```

`argv` keeps `{prompt}` **unsubstituted** — the plan is descriptive, not runnable.

## No-remote-execution guarantee

This API never spawns a process. There is no "execute" endpoint — only
`/v1/execute/dry-run`, which reads a stored decision and returns the argv/plan
that *would* run. `would_execute` is always `false`. Host detection (`/v1/hosts`,
and availability in `/v1/models`) is presence-only: it checks `PATH` / env-var
presence and never reads secret values or contacts a provider. Actual execution
remains a deliberate, human-gated CLI action (`agentrouter execute`).

## Python SDK

```python
from agentrouter.sdk import AgentRouterClient

with AgentRouterClient("http://127.0.0.1:8000", api_key="your-secret") as client:
    client.health()
    models = client.models()
    decision = client.route("summarize this PDF", prefer="cheap")
    client.feedback(decision["decision_id"], rating=5)
    plan = client.execute_dry_run(decision["decision_id"])  # never runs anything
```

Non-2xx responses raise `AgentRouterError` (with `.status_code` and `.code`).

## Limitations

- **Rate limiting** is documented as a requirement but not enforced in-process;
  put the app behind a reverse proxy if you need it. The API is intended for
  localhost use.
- **Feedback** is stored in the existing SQLite `feedback` table via a direct
  insert (no new storage layer added); it is validated against an existing
  decision first.
- The registry is loaded per request (simple and always fresh); add caching if
  latency matters under load.
