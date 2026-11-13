# Rust HTTP server migration preview

The Rust HTTP server is an integration and compatibility preview. The Python
FastAPI service remains the supported release implementation until the Rust
server passes the complete API contract, client, platform, and release gates.

## Start it locally

Initialize the local registry with the Python CLI, then run the Rust server from
the repository workspace:

```bash
agentrouter init
cargo run --locked -p agentrouter-api --bin agentrouter-api-server
```

It binds to `127.0.0.1:8787` by default and reads the same `AGENTROUTER_HOME`
directory as the CLI. Override the bind address or home with `--bind` and
`--home`:

```bash
cargo run --locked -p agentrouter-api --bin agentrouter-api-server -- \
  --bind 127.0.0.1:8787 --home "$HOME/.agentrouter"
```

The process handles Ctrl-C with graceful shutdown. It does not execute model or
host commands. `/v1/execute/dry-run` only returns a preview.

## Check the TypeScript client

The repository test harness can run the TypeScript SDK against either server.
To exercise the Rust process after building the workspace:

```bash
npm ci --prefix sdk/typescript
AGENTROUTER_REQUIRE_LIVE=1 AGENTROUTER_PARITY_SERVER=rust \
  AGENTROUTER_PYTHON=python npm test --prefix sdk/typescript
```

The harness initializes an isolated temporary registry, launches the compiled
Rust API on loopback, and exercises every operation in the SDK capability
manifest. Rust CI runs this check on Linux, Windows, and macOS.

## Local protections

- `/v1/*` is open unless `AGENTROUTER_API_KEY` is set; then requests need a
  matching `X-API-Key` header.
- Browser access is disabled by default. `AGENTROUTER_CORS_ORIGINS` accepts a
  comma-separated allowlist of exact origins; wildcard origins are ignored.
- `AGENTROUTER_RATE_LIMIT` enables process-local fixed-window request limits;
  `/health` and `/ready` are exempt. `AGENTROUTER_RATE_WINDOW` defaults to 60
  seconds.
- `Idempotency-Key` on a POST enables successful-response replay for the
  caller, route, and request body. `AGENTROUTER_IDEMPOTENCY_TTL` defaults to
  300 seconds. Idempotent request bodies and individually cached response
  bodies are capped at 1 MiB; the in-memory response cache is limited to
  10,000 entries and 16 MiB total body data.

This preview binds to loopback and does not provide TLS, shared multi-process
rate limits, or remote deployment configuration. Keep it local until those
release requirements and the remaining API parity work are complete.
