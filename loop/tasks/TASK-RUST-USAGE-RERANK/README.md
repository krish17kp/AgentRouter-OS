# Rust usage-aware reranking parity slice

Date: 2026-11-11

## Scope

Port `agentrouter.usage.apply_live_verification` into `agentrouter-usage`.
The Rust helper checks the recommended provider with the existing bounded,
isolated status mechanism. Unsupported, available, and error states preserve the
route. An exhausted status excludes only the current top model and reranks once;
the response includes the same quota annotation, exclusion reason, and weight
shift as Python. Eligibility exclusions are not duplicated, and a route with no
recommendation is returned without a usage annotation.

`apply_usage_status` is a deterministic seam for offline tests. The companion
`usage_route_from_json` binary accepts fixture data only; it performs no
network calls and does not register a production adapter.
The Rust `route_cli --verify-live` option wires the same behavior into the
route-command probe and returns the `usage_check` result alongside the route.

## Evidence

- Eight Rust usage unit tests pass, including exhaustion reranking, invalid
  state fail-closed behavior, unsupported preservation, no-pick behavior,
  adapter timeout, panic isolation, and status registration.
- Nine Python/Rust differential tests compare full serialized results for
  exhausted, unsupported, and no-recommendation routes, including Python's
  `str.isprintable()` sanitation behavior for control, separator, format, and
  private-use characters. The route CLI has a separate `--verify-live` parity
  case.
- Rust workspace tests, Clippy, and formatting pass locally. Full Python suite
  passed before the Unicode differential expansion and is rerunning now.
- No live provider adapter is enabled. OpenAI quota validation remains an
  owner credential and bounded paid-test requirement.

## Limits

This remains a migration slice in the Rust route-command probe, not a provider
integration. No production usage adapter is enabled; the route option returns
an honest `unsupported` result for real providers until a bounded, credentialed
adapter is added and validated. Keep this module marked partial until the Rust
command ships in a supported distribution and the provider adapter path is
complete.
