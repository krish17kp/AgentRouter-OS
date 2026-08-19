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

| Code | Status | Meaning |
|------|--------|---------|
| `unauthorized` | 401 | Missing or wrong `X-API-Key` while `AGENTROUTER_API_KEY` is set |
| `not_found` | 404 | No such decision, or no such route |
| `validation_error` | 422 | The request body failed validation; `message` names the field |
| `rate_limited` | 429 | Opt-in rate limit exceeded; retry after `Retry-After` seconds |
| `registry_unavailable` | 503 | The local registry is missing or malformed — run `agentrouter doctor` |
| `internal_error` | 500 | An unexpected server-side fault |
| `error` | other | Any other HTTP error |

`message` is safe to display but is **not** a stable API: match on `code`.

Two codes deliberately say less than the server knows. `registry_unavailable`
and `internal_error` both carry a fixed message, because the underlying text
quotes registry file paths and the offending source line — and a registry is
only malformed at exactly the moment someone has pasted a credential into it.
The detail is written to the server log at `ERROR` with the request id, so run
`agentrouter doctor` locally, or correlate the `X-Request-ID` with the log.
**No traceback is ever returned to a client.**

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

## Compatibility promise

`GET /openapi.json` describes whatever the running process happens to serve. The
**contract** is the committed artifact at `contracts/http/v1/openapi.json`, with
its provenance in `contracts/http/v1/manifest.json`. It is regenerated from the
real app, canonicalised (recursively sorted, environment-dependent fields
dropped) so it is byte-stable, and carries no timestamp or commit — those live in
the manifest, so an unchanged API produces an unchanged file.

```bash
agentrouter contract check          # live app vs the committed contract
agentrouter contract check --json   # machine-readable report
agentrouter contract export         # regenerate after an intentional change
```

`contract check` exit codes: `0` compatible (or every break owner-accepted),
`1` breaking change, `3` missing or
untrustworthy baseline, `4` this install has no HTTP API to describe (the
`[server]` extra is absent). A missing baseline is a failure, never a pass, and
`4` is deliberately not `1` so CI cannot mistake "the extra was not installed"
for "the API broke". CI runs it on every push and the enforced release gate
depends on it.

Changes are classified into three bands:

| Band | Examples | Effect |
|------|----------|--------|
| **breaking** | endpoint/method/media-type/parameter removed; a **response** field removed or made optional; a **request** field made required, or its enum/`const` introduced or narrowed, constraint or `format` tightened, body made required, `additionalProperties` closed; a type change; a request stops accepting `null`; a response starts returning `null`; authentication removed or a scheme redefined (including oauth2 `flows`); `servers` relocated | Fails CI |
| **accepted** | a breaking change the owner reviewed and recorded via `--accept-breaking --reason`, matched on the checker's own (kind, location) | Reported prominently, does not fail |
| **risky** | a **request** enum expanded or unconstrained; a **response** enum expanded or removed; type erased to untyped; `default`/`format` changed on a response; `operationId` renamed; an operation deprecated; a status wildcard refined into explicit codes; description changes; `info.version` changed | Reported, does not fail |
| **additive** | new endpoint; a new **response** field (even a required one — a stronger promise, not a client break); a new optional request field; a newly documented response status; a request constraint relaxed; a **response** enum narrowed; an additional accepted auth scheme | Reported, does not fail |

Direction matters throughout, because the same edit means opposite things on the
two sides of a call. `required` on a request is an obligation on the caller; on a
response it is a guarantee from the server. A narrowed enum rejects callers on a
request but merely promises less on a response. `allOf` is a conjunction, so more
branches is *narrower*, while `anyOf`/`oneOf` gain permissiveness with more.

`required` is read per direction, because it means opposite things: on a request
it is an obligation on the caller, on a response it is a guarantee from the
server. Treating a new required response field as breaking would fail CI on the
most common additive change there is, and teach maintainers to reach for
`--accept-breaking` — which is how a gate stops meaning anything.

A deliberate breaking change is not silently absorbed: `contract export` refuses
to overwrite the baseline while a breaking change is present, and recording one
requires `--accept-breaking --reason "<owner-reviewed justification>"`. That
appends to `accepted_breaking_changes` in the manifest, which a later routine
export will not erase and which can only record a break the checker itself
detected. `contract check` then reads that record: a break matching a recorded
(kind, location) is reported as **accepted** rather than failing, so the decision
can actually ship. Any *other* break in the same change still fails — an
acceptance excuses exactly what it names, and nothing else.

CI also checks the live app against the contract on the **base branch**, not just
the copy in the branch under review. Without that, the branch grades its own
homework: deleting or corrupting `contracts/http/v1/openapi.json` would make any
breaking change look green.

### What `contracts/http/v1/` means

`v1` is the version of **this contract artifact**, not a second HTTP API. There is
one running app and one exported document, which describes every path it serves —
including the unversioned `/health` and `/ready` probes. Creating
`contracts/http/v2/` would not route a `/v2` API into existence; it would only
produce a second file describing the same app.

So when a genuinely incompatible API arrives, the versioning happens in the
**URL space** (`/v2/...` paths added alongside `/v1/...`, both described by the
one contract, with `endpoint_removed` protecting the old paths until they are
deliberately retired) — not by adding a directory here.

### SDK parity

`contracts/sdk/capabilities.json` is the versioned record of which operations
each SDK supports. Every operation listed is *exercised* against the real app, so
an entry cannot claim coverage the SDK does not have — Python drives an
in-process uvicorn server, TypeScript drives the same app started by
`scripts/serve_for_parity.py` (Node cannot host an ASGI app in-process, so it is
the real app over loopback rather than literally in-process). CI sets
`AGENTROUTER_REQUIRE_LIVE=1` so a skipped live suite fails instead of passing.

### What the checker still cannot see

Stated plainly, because a compatibility gate that is trusted beyond its reach is
worse than one whose limits are known:

- **Semantics.** Anything not expressible in OpenAPI — a field whose *meaning*
  changes, an id format, ordering guarantees, pagination behaviour, rate-limit
  thresholds. `/v1/decisions/{id}` replays an opaque engine payload, so the
  contract describes its top-level keys and nothing deeper.
- **Structures it does not model:** response `headers`, path-item-level
  `parameters`, `webhooks`/`callbacks`, `discriminator`, and
  `readOnly`/`writeOnly`.
- **Multi-branch unions** are compared branch-by-branch when both sides have the
  same combinator and the same number of alternatives. When the arity or the
  combinator differs, the *shape* change is reported (`union_widened` /
  `union_narrowed`, direction-aware — `allOf` is a conjunction, so more branches
  is narrower) but the branches are not matched up individually. The common
  `T | None` shape is fully unwrapped and compared.
- **`not`**, parameter `style`/`explode`/`deprecated`, and the *scope* granularity
  of a security requirement are not compared at all.
- **Behaviour under load or failure** — that is TASK-018B, not this gate.

## Limitations

- **Rate limiting** is enforced in-process but opt-in and single-process: set
  `AGENTROUTER_RATE_LIMIT` (requests per `AGENTROUTER_RATE_WINDOW`, default 60s)
  to enable it. The counters live in one process's memory, so behind multiple
  workers each gets its own budget — put the app behind a reverse proxy if you
  need a shared limit. The API is intended for localhost use.
- **Feedback** is stored in the existing SQLite `feedback` table via a direct
  insert (no new storage layer added); it is validated against an existing
  decision first.
- The registry is loaded per request (simple and always fresh); add caching if
  latency matters under load.
