import { fixtures, type RoutingFixture } from './data'
export type RouteRequest = { task: string; context_tokens?: number; risk?: 'low' | 'medium' | 'high'; tools?: string[] }
export type RoutingSource = 'recorded-cli' | 'local-api'
export type RouteResult = { source: RoutingSource; result: RoutingFixture }

const configuredApiUrl = import.meta.env.VITE_AGENTROUTER_API_URL?.trim().replace(/\/$/, '')

export function localApiEnabled(): boolean { return Boolean(configuredApiUrl) }

function providerFromModel(model: string): string {
  return model.includes('/') ? model.split('/', 1)[0] : 'local registry'
}

function asFixture(payload: unknown): RoutingFixture {
  if (!payload || typeof payload !== 'object') throw new Error('The local API returned an invalid route response.')
  const response = payload as Record<string, unknown>
  const classification = response.classification as Record<string, unknown> | null
  const recommendation = response.recommendation as Record<string, unknown> | null
  const fallback = response.fallback as Record<string, unknown> | null
  if (!classification || !recommendation || !fallback || typeof response.task !== 'string') {
    throw new Error('The local API did not return a recommendation and fallback.')
  }
  const model = String(recommendation.model ?? '')
  const fallbackModel = String(fallback.model ?? '')
  if (!model || !fallbackModel) throw new Error('The local API returned an incomplete route response.')
  const scores = Array.isArray(response.scores) ? response.scores : []
  return {
    task: response.task,
    classification: {
      task_type: String(classification.task_type ?? 'unknown'),
      complexity: String(classification.complexity ?? 'unknown'),
      risk: String(classification.risk ?? 'unknown'),
      context_band: String(classification.context_band ?? 'unknown'),
      approval_level: String(classification.approval_level ?? 'unknown'),
    },
    recommendation: { model, provider: providerFromModel(model), score: Number(recommendation.score ?? 0) },
    fallback: { model: fallbackModel, provider: providerFromModel(fallbackModel), score: Number(fallback.score ?? 0) },
    scores: scores.flatMap((item) => {
      if (!item || typeof item !== 'object') return []
      const row = item as Record<string, unknown>
      const rowModel = String(row.model ?? '')
      return rowModel ? [{ model: rowModel, provider: providerFromModel(rowModel), score: Number(row.score ?? 0), pricing_tier: String(row.pricing_tier ?? 'unknown') }] : []
    }),
    excluded: [],
  }
}

export async function routeDemo(request: RouteRequest): Promise<RouteResult> {
  const fixture = fixtures.find((item) => item.task === request.task)
  if (!fixture) throw new Error('Recorded mode only supports the three example prompts. Configure a local API to route custom text.')
  return { source: 'recorded-cli', result: fixture }
}

export async function routeLocal(request: RouteRequest): Promise<RouteResult> {
  if (!configuredApiUrl) throw new Error('No local API URL is configured.')
  const response = await fetch(`${configuredApiUrl}/v1/route`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // Browser routes are intentionally ephemeral: the local API must not persist
    // visitor task text or a generated prompt unless the user uses its own CLI/API.
    body: JSON.stringify({ ...request, no_log: true }),
  })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'error' in payload
      ? String((payload.error as { message?: unknown }).message ?? 'Route request failed.')
      : 'Route request failed.'
    throw new Error(message)
  }
  return { source: 'local-api', result: asFixture(payload) }
}
