import { fixtures, type RoutingFixture } from './data'
export type RouteRequest = { task: string; context_tokens?: number; risk?: 'low' | 'medium' | 'high'; tools?: string[] }
export type RoutingSource = 'recorded-cli' | 'local-api'
export type RouteResult = { source: RoutingSource; result: RoutingFixture }
// Public demo intentionally never transmits visitor tasks. Future versioned API integration uses this seam.
export async function routeDemo(request: RouteRequest): Promise<RouteResult> { return { source: 'recorded-cli', result: fixtures.find((f) => f.task === request.task) ?? fixtures[0] } }
