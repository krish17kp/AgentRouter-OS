/** Contract tests for the TypeScript SDK (backlog L3). Mock fetch — no server needed. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { AgentRouterClient, AgentRouterError } from "../src/index.ts";

interface Call {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: unknown;
}

function mockFetch(status: number, payload: unknown) {
  const calls: Call[] = [];
  const impl = (async (url: string | URL | Request, init?: RequestInit) => {
    const h = (init?.headers ?? {}) as Record<string, string>;
    calls.push({
      url: String(url),
      method: init?.method ?? "GET",
      headers: h,
      body: init?.body ? JSON.parse(init.body as string) : undefined,
    });
    return new Response(JSON.stringify(payload), {
      status,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
  return { impl, calls };
}

test("route posts to /v1/route with a cleaned body (keeps no_log:false, drops undefined)", async () => {
  const { impl, calls } = mockFetch(200, { decision_id: "d_1", recommendation: { model: "m" } });
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  const out = await client.route("summarize a PR");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].method, "POST");
  assert.equal(calls[0].url, "http://x/v1/route");
  assert.deepEqual(calls[0].body, { task: "summarize a PR", no_log: false });
  assert.equal((out as { decision_id: string }).decision_id, "d_1");
});

test("classify drops undefined options but keeps provided ones", async () => {
  const { impl, calls } = mockFetch(200, { task_type: "coding" });
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await client.classify("refactor auth", { risk: "high" });
  assert.deepEqual(calls[0].body, { task: "refactor auth", risk: "high" });
});

test("non-2xx raises AgentRouterError carrying status + code", async () => {
  const { impl } = mockFetch(404, { error: { code: "not_found", message: "no decision" } });
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await assert.rejects(
    () => client.getDecision("d_missing"),
    (e: unknown) => {
      assert.ok(e instanceof AgentRouterError);
      assert.equal(e.status, 404);
      assert.equal(e.code, "not_found");
      return true;
    },
  );
});

test("non-JSON error body still raises AgentRouterError (proxy/gateway pages)", async () => {
  const impl = (async () =>
    new Response("Internal Server Error", {
      status: 502,
      headers: { "content-type": "text/plain" },
    })) as unknown as typeof fetch;
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await assert.rejects(
    () => client.health(),
    (e: unknown) => {
      assert.ok(e instanceof AgentRouterError);
      assert.equal(e.status, 502);
      assert.equal(e.code, "error");
      assert.match(e.message, /Internal Server Error/);
      return true;
    },
  );
});

test("api key is sent as X-API-Key", async () => {
  const { impl, calls } = mockFetch(200, { status: "ok" });
  const client = new AgentRouterClient("http://x", { apiKey: "secret", fetchImpl: impl });
  await client.health();
  assert.equal(calls[0].headers["X-API-Key"], "secret");
});

test("base url trailing slash is stripped", async () => {
  const { impl, calls } = mockFetch(200, []);
  const client = new AgentRouterClient("http://x/", { fetchImpl: impl });
  await client.models();
  assert.equal(calls[0].url, "http://x/v1/models");
});

test("getDecision GETs the url-encoded id", async () => {
  const { impl, calls } = mockFetch(200, { decision_id: "d_1" });
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await client.getDecision("d 1");
  assert.equal(calls[0].method, "GET");
  assert.equal(calls[0].url, "http://x/v1/decisions/d%201");
});

test("feedback posts decision_id + rating and drops undefined note", async () => {
  const { impl, calls } = mockFetch(200, { recorded: true });
  const client = new AgentRouterClient("http://x", { fetchImpl: impl });
  await client.feedback("d_1", 5);
  assert.deepEqual(calls[0].body, { decision_id: "d_1", rating: 5 });
});
