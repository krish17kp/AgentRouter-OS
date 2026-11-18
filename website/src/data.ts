export type RoutingFixture = {
  task: string; classification: { task_type: string; complexity: string; risk: string; context_band: string; approval_level: string }
  recommendation: { model: string; provider: string; score: number }; fallback: { model: string; provider: string; score: number }
  scores: { model: string; provider: string; score: number; pricing_tier: string }[]; excluded: { model: string; reason: string }[]
}

// These recorded, privacy-safe examples mirror the documented routing response shape.
// The browser never posts tasks to an AgentRouter server or claims live inference.
export const fixtures: RoutingFixture[] = [
  { task: 'Review this Python repository for security issues.', classification: { task_type: 'analysis', complexity: 'medium', risk: 'medium', context_band: 'medium', approval_level: 'notify' }, recommendation: { model: 'anthropic/claude-sonnet-5', provider: 'anthropic', score: .867 }, fallback: { model: 'anthropic/claude-haiku-4-5-20251001', provider: 'anthropic', score: .74 }, scores: [{model:'anthropic/claude-sonnet-5',provider:'anthropic',score:.867,pricing_tier:'high'},{model:'openai/gpt-5.6-terra',provider:'openai',score:.867,pricing_tier:'high'},{model:'anthropic/claude-opus-4-8',provider:'anthropic',score:.847,pricing_tier:'frontier'}], excluded: [] },
  { task: 'Generate unit tests for an existing application.', classification: { task_type: 'coding', complexity: 'low', risk: 'low', context_band: 'medium', approval_level: 'auto' }, recommendation: { model: 'anthropic/claude-haiku-4-5-20251001', provider: 'anthropic', score: .885 }, fallback: { model: 'anthropic/claude-sonnet-5', provider: 'anthropic', score: .71 }, scores: [{model:'anthropic/claude-haiku-4-5-20251001',provider:'anthropic',score:.885,pricing_tier:'low'},{model:'openai/gpt-5.6-luna',provider:'openai',score:.78,pricing_tier:'medium'},{model:'anthropic/claude-sonnet-5',provider:'anthropic',score:.71,pricing_tier:'high'}], excluded: [] },
  { task: 'Explain a complex database architecture.', classification: { task_type: 'reasoning', complexity: 'medium', risk: 'medium', context_band: 'small', approval_level: 'notify' }, recommendation: { model: 'anthropic/claude-opus-4-8', provider: 'anthropic', score: .86 }, fallback: { model: 'anthropic/claude-sonnet-5', provider: 'anthropic', score: .83 }, scores: [{model:'anthropic/claude-opus-4-8',provider:'anthropic',score:.86,pricing_tier:'frontier'},{model:'openai/gpt-5.6-sol',provider:'openai',score:.86,pricing_tier:'frontier'},{model:'openai/gpt-5.6-luna',provider:'openai',score:.835,pricing_tier:'medium'}], excluded: [] }
]

export const features = [
  ['Explainable routing','Every decision carries a ranked, inspectable trail.'], ['Local-first','Route privately, with no cloud inference required.'], ['Policy-aware','Hard constraints filter candidates before scoring.'], ['Host-aware','Recommendations account for usable execution environments.'], ['MCP integration','Read-only routing surfaces support compatible MCP clients.'], ['Safe by default','High-risk work is routed with human approval gates.']
]
