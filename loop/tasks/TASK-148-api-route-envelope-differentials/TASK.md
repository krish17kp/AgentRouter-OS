# TASK-148 — Expand Rust API route-envelope differential cases

## Goal

Increase confidence that the Rust API service composes the same route response
as Python across high-risk safety gates and explicit routing preferences.

## Scope

- Add differential cases for a high-risk route with a filesystem tool need and
  a medium-risk route using the `quality` preference.
- Compare the complete serialized response envelope, including classification,
  recommendation, fallback, score details, gates, prompt, and execution-route
  information.
- Keep `agentrouter/server/service.py` and the Rust API service tracked as
  Partial. These cases do not cover Python logging/span side effects or the full
  FastAPI lifecycle and middleware contract.

## Acceptance

- Both new Python/Rust route scenarios produce equal JSON values.
- The existing route preview differential remains green.
- No frozen evaluation data or release thresholds change.
- Hosted Linux, Windows, and macOS validation passes after push.
