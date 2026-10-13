/**
 * Tiny typed TypeScript SDK for the local AgentRouter REST API (backlog L3).
 *
 *   import { AgentRouterClient } from "@agentrouter/sdk";
 *   const client = new AgentRouterClient("http://127.0.0.1:8000");
 *   await client.route("summarize this PR");
 *
 * Contract parity with the Python SDK (agentrouter/sdk.py): same endpoints, same
 * error shape ({"error": {...}} -> AgentRouterError), same body-cleaning rules.
 */

/** Raised for non-2xx responses; carries the HTTP status and server error code. */
export class AgentRouterError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(`[${status}] ${code}: ${message}`);
    this.name = "AgentRouterError";
    this.status = status;
    this.code = code;
  }
}

export interface ClientOptions {
  apiKey?: string;
  timeoutMs?: number;
  /** Injectable fetch (defaults to global fetch) — used for tests. */
  fetchImpl?: typeof fetch;
}

export interface ClassifyOptions {
  contextTokens?: number;
  risk?: string;
  tools?: string[];
}

export interface RouteOptions extends ClassifyOptions {
  prefer?: string;
  noLog?: boolean;
}

export interface HealthResponse {
  status: string;
}

export interface ModelSummary {
  vendor: string;
  model_id: string;
  key: string;
  release_channel: string;
  context_window: number;
  host_availability: string;
}

/** Server responses are otherwise passed through as plain objects. */
export type Json = Record<string, unknown>;

/** Drop undefined/null so server defaults apply; keep explicit false/0 (parity with _clean). */
function clean(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined && v !== null),
  );
}

export class AgentRouterClient {
  private readonly baseUrl: string;
  private readonly headers: Record<string, string>;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(baseUrl = "http://127.0.0.1:8000", opts: ClientOptions = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.headers = opts.apiKey ? { "X-API-Key": opts.apiKey } : {};
    this.timeoutMs = opts.timeoutMs ?? 10_000;
    this.fetchImpl = opts.fetchImpl ?? fetch;
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { ...this.headers };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let resp: Response;
    try {
      resp = await this.fetchImpl(this.baseUrl + path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
    const text = await resp.text();
    // Parse defensively: a non-2xx from a proxy/gateway may be non-JSON (HTML/plain).
    // Mirror the Python SDK's `try/except ValueError` so such bodies still surface as
    // AgentRouterError rather than an uncaught SyntaxError.
    let data: any = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = {};
    }
    if (!resp.ok) {
      const err = (data?.error ?? {}) as { code?: string; message?: string };
      throw new AgentRouterError(resp.status, err.code ?? "error", err.message ?? text);
    }
    return data as T;
  }

  health(): Promise<HealthResponse> {
    return this.request("GET", "/health");
  }

  ready(): Promise<HealthResponse> {
    return this.request("GET", "/ready");
  }

  models(): Promise<ModelSummary[]> {
    return this.request("GET", "/v1/models");
  }

  hosts(): Promise<Json[]> {
    return this.request("GET", "/v1/hosts");
  }

  classify(task: string, opts: ClassifyOptions = {}): Promise<Json> {
    return this.request("POST", "/v1/classify", clean({
      task,
      context_tokens: opts.contextTokens,
      risk: opts.risk,
      tools: opts.tools,
    }));
  }

  route(task: string, opts: RouteOptions = {}): Promise<Json> {
    return this.request("POST", "/v1/route", clean({
      task,
      prefer: opts.prefer,
      context_tokens: opts.contextTokens,
      risk: opts.risk,
      tools: opts.tools,
      no_log: opts.noLog ?? false, // parity: Python SDK always sends no_log (default False)
    }));
  }

  getDecision(decisionId: string): Promise<Json> {
    return this.request("GET", `/v1/decisions/${encodeURIComponent(decisionId)}`);
  }

  feedback(decisionId: string, rating: number, note?: string): Promise<Json> {
    return this.request("POST", "/v1/feedback", clean({
      decision_id: decisionId,
      rating,
      note,
    }));
  }

  executeDryRun(decisionId: string): Promise<Json> {
    return this.request("POST", "/v1/execute/dry-run", { decision_id: decisionId });
  }
}
