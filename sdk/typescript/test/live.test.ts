/**
 * TypeScript SDK against the REAL AgentRouter app (TASK-018A).
 *
 * parity.test.ts asserts the requests this client *builds*. That cannot catch a
 * client that builds a well-formed request the server rejects — a body shape the
 * app 422s would still pass a recorded-transport test. So every operation the
 * capability manifest claims is driven here over loopback against the genuine
 * ASGI app, started by scripts/serve_for_parity.py in a throwaway home.
 *
 * No external network, no credentials, no paid calls.
 *
 * If Python or the [server] extra is unavailable the suite skips — except when
 * AGENTROUTER_REQUIRE_LIVE=1, which CI sets so a skip can never be mistaken for
 * a pass.
 */

import assert from "node:assert/strict";
import { spawn, type ChildProcessByStdio } from "node:child_process";
import type { Readable } from "node:stream";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

import { AgentRouterClient, AgentRouterError } from "../src/index.ts";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..");
const requireLive = process.env.AGENTROUTER_REQUIRE_LIVE === "1";
const pythonBin = process.env.AGENTROUTER_PYTHON ?? "python3";

const capabilities = JSON.parse(
  readFileSync(join(repoRoot, "contracts", "sdk", "capabilities.json"), "utf8"),
) as { operations: Array<{ id: string; method: string; path: string; typescript: string }> };

let server: ChildProcessByStdio<null, Readable, Readable> | undefined;
let baseUrl = "";
let startupError = "";

/** Start the real app and resolve once it prints its URL. */
function startServer(): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin, [join(repoRoot, "scripts", "serve_for_parity.py")], {
      cwd: repoRoot,
      stdio: ["ignore", "pipe", "pipe"],
    });
    server = child;

    let stderr = "";
    const timer = setTimeout(() => reject(new Error(`server did not start in 60s: ${stderr}`)), 60_000);

    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      const match = /PARITY_SERVER_URL=(\S+)/.exec(chunk);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`server exited with ${code}: ${stderr}`));
    });
  });
}

before(async () => {
  try {
    baseUrl = await startServer();
  } catch (err) {
    startupError = err instanceof Error ? err.message : String(err);
    if (requireLive) {
      throw new Error(
        `AGENTROUTER_REQUIRE_LIVE=1 but the live app could not be started: ${startupError}`,
      );
    }
  }
});

after(() => {
  server?.kill("SIGTERM");
});

/** Skip cleanly when the app is unavailable and CI has not demanded it. */
function live(): { skip: string } | undefined {
  return baseUrl ? undefined : { skip: `live app unavailable: ${startupError}` };
}

test("every manifest operation succeeds against the real app", async (t) => {
  const reason = live();
  if (reason) return t.skip(reason.skip);

  const client = new AgentRouterClient(baseUrl);
  const exercised = new Set<string>();

  assert.equal((await client.health()).status, "ok");
  exercised.add("health");
  assert.equal((await client.ready()).status, "ready");
  exercised.add("ready");

  const models = (await client.models()) as unknown as Array<Record<string, unknown>>;
  assert.ok(models.length > 0, "the seeded registry must expose at least one model");
  assert.ok("model_id" in models[0] && "host_availability" in models[0]);
  exercised.add("models");

  const hosts = (await client.hosts()) as unknown as Array<Record<string, unknown>>;
  assert.ok(hosts.length > 0);
  // additive TASK-016 fields must survive the round trip to a TS client
  assert.ok("state" in hosts[0] && "remedy" in hosts[0]);
  exercised.add("hosts");

  const classified = (await client.classify("write a haiku about routers")) as Record<string, unknown>;
  assert.ok("task_type" in classified);
  exercised.add("classify");

  const routed = (await client.route("write a haiku about routers")) as Record<string, unknown>;
  const decisionId = routed.decision_id as string;
  assert.ok(decisionId, "route must return a decision id");
  // engine-owned keys must not be stripped by the server's response model
  for (const key of ["classification", "recommendation", "scores", "gates"]) {
    assert.ok(key in routed, `route response lost ${key}`);
  }
  exercised.add("route");

  const fetched = (await client.getDecision(decisionId)) as Record<string, unknown>;
  assert.equal(fetched.decision_id, decisionId);
  exercised.add("get_decision");

  assert.equal(((await client.feedback(decisionId, 5)) as Record<string, unknown>).recorded, true);
  exercised.add("feedback");

  const plan = (await client.executeDryRun(decisionId)) as Record<string, unknown>;
  assert.equal(plan.would_execute, false, "dry-run must never report execution");
  exercised.add("execute_dry_run");

  const claimed = capabilities.operations.map((o) => o.id).sort();
  assert.deepEqual([...exercised].sort(), claimed, "a claimed operation was never exercised live");
});

test("a real 404 from the app surfaces as a typed error", async (t) => {
  const reason = live();
  if (reason) return t.skip(reason.skip);

  const client = new AgentRouterClient(baseUrl);
  await assert.rejects(
    () => client.getDecision("d_does_not_exist"),
    (err: unknown) =>
      err instanceof AgentRouterError && err.status === 404 && err.code === "not_found",
  );
});

test("a real validation failure surfaces as a typed 422", async (t) => {
  const reason = live();
  if (reason) return t.skip(reason.skip);

  const client = new AgentRouterClient(baseUrl);
  await assert.rejects(
    () => client.feedback("d_00001", 99), // rating is bounded 1..5
    (err: unknown) =>
      err instanceof AgentRouterError && err.status === 422 && err.code === "validation_error",
  );
});

test("the app returns a correlatable request id to a TS client", async (t) => {
  const reason = live();
  if (reason) return t.skip(reason.skip);

  const response = await fetch(`${baseUrl}/health`, { headers: { "X-Request-ID": "ts-trace" } });
  assert.equal(response.headers.get("X-Request-ID"), "ts-trace");
});
