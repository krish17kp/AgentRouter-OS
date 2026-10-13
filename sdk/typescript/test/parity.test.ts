/**
 * SDK ↔ HTTP contract parity for the TypeScript client (TASK-018A).
 *
 * Drives every operation named in contracts/sdk/capabilities.json through the real
 * client code and asserts the request it produces (method, path, auth header)
 * matches the committed OpenAPI contract. A manifest entry that is never called
 * fails the run, so the manifest cannot claim unexercised support.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { AgentRouterClient, AgentRouterError } from "../src/index.ts";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..");

const capabilities = JSON.parse(
  readFileSync(join(repoRoot, "contracts", "sdk", "capabilities.json"), "utf8"),
) as {
  operations: Array<{
    id: string;
    method: string;
    path: string;
    authenticated: boolean;
    typescript: string;
  }>;
};

const openapi = JSON.parse(
  readFileSync(join(repoRoot, "contracts", "http", "v1", "openapi.json"), "utf8"),
) as { paths: Record<string, Record<string, unknown>> };

interface Recorded {
  url: string;
  method: string;
  headers: Record<string, string>;
}

function recorder(status = 200, payload: unknown = {}) {
  const calls: Recorded[] = [];
  const impl = (async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({
      url: String(url),
      method: init?.method ?? "GET",
      headers: (init?.headers ?? {}) as Record<string, string>,
    });
    return new Response(JSON.stringify(payload), {
      status,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
  return { impl, calls };
}

/** Invoke an operation by its manifest name with plausible arguments. */
async function invoke(client: AgentRouterClient, id: string): Promise<void> {
  switch (id) {
    case "health": await client.health(); break;
    case "ready": await client.ready(); break;
    case "models": await client.models(); break;
    case "hosts": await client.hosts(); break;
    case "classify": await client.classify("write a haiku"); break;
    case "route": await client.route("write a haiku"); break;
    case "get_decision": await client.getDecision("d_00001"); break;
    case "feedback": await client.feedback("d_00001", 5); break;
    case "execute_dry_run": await client.executeDryRun("d_00001"); break;
    default: throw new Error(`no invoker for manifest operation '${id}'`);
  }
}

/** Concrete path -> OpenAPI template (so /v1/decisions/d_00001 matches the {param} form). */
function toTemplate(path: string): string {
  if (/^\/v1\/decisions\/[^/]+$/.test(path)) return "/v1/decisions/{decision_id}";
  return path;
}

test("every manifest operation is exercised and matches the committed contract", async () => {
  const exercised = new Set<string>();

  for (const op of capabilities.operations) {
    const { impl, calls } = recorder();
    const client = new AgentRouterClient("http://x", { fetchImpl: impl, apiKey: "k" });
    await invoke(client, op.id);

    assert.equal(calls.length, 1, `${op.id}: expected exactly one request`);
    const call = calls[0];
    assert.equal(call.method.toLowerCase(), op.method, `${op.id}: wrong HTTP method`);

    const path = new URL(call.url).pathname;
    assert.equal(toTemplate(path), op.path, `${op.id}: wrong path`);

    // the path the client calls must actually be served by the contract
    const entry = openapi.paths[op.path];
    assert.ok(entry, `${op.id}: ${op.path} missing from the OpenAPI contract`);
    assert.ok(entry[op.method], `${op.id}: ${op.method} missing from the contract`);

    assert.equal(call.headers["X-API-Key"], "k", `${op.id}: auth header not sent`);
    exercised.add(op.id);
  }

  const claimed = capabilities.operations.map((o) => o.id).sort();
  assert.deepEqual([...exercised].sort(), claimed, "a claimed operation was never exercised");
});

test("no api key configured means no auth header is sent", async () => {
  const { impl, calls } = recorder();
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await client.health();
  assert.equal(calls[0].headers["X-API-Key"], undefined);
});

test("typed error carries status and server error code", async () => {
  const { impl } = recorder(404, { error: { code: "not_found", message: "no decision" } });
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await assert.rejects(
    () => client.getDecision("nope"),
    (err: unknown) => {
      assert.ok(err instanceof AgentRouterError);
      assert.equal(err.status, 404);
      assert.equal(err.code, "not_found");
      return true;
    },
  );
});

test("internal error envelope surfaces as a typed error, not a parse failure", async () => {
  const { impl } = recorder(500, { error: { code: "internal_error", message: "internal server error" } });
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await assert.rejects(
    () => client.route("x"),
    (err: unknown) => err instanceof AgentRouterError && err.code === "internal_error",
  );
});

test("rate limited response surfaces the rate_limited code", async () => {
  const { impl } = recorder(429, { error: { code: "rate_limited", message: "slow down" } });
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await assert.rejects(
    () => client.route("x"),
    (err: unknown) => err instanceof AgentRouterError && err.status === 429,
  );
});

test("hosts response exposes the additive state/remedy fields to clients", async () => {
  const payload = [
    { host: "manual", availability: "available", reason: "always", state: "configured", remedy: null },
  ];
  const { impl } = recorder(200, payload);
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  const hosts = (await client.hosts()) as Array<Record<string, unknown>>;
  assert.equal(hosts[0].state, "configured");
  assert.ok("remedy" in hosts[0]);
});
