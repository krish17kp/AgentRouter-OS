# Graphify baseline — AgentRouter OS

- Built: 2026-07-20 via `graphify update .` (graphifyy 0.9.30).
- Commit at build: `602321af91ff298c0d5b59d6d36c24f845557fc1` + uncommitted v0.5-rc working tree.
- Source: `graphify-out/graph.json` (gitignored; rebuild with `graphify update .`).

## Size

| metric | value |
|---|---:|
| nodes | 2271 |
| links | 4262 |
| source files | 281 |
| communities | 238 |

## Relation (edge) kinds

`contains` 1498, `calls` 1242, `references` 386, `imports` 374, `rationale_for` 295,
`imports_from` 213, `method` 100, `inherits` 66, `uses` 44, `indirect_call` 30, `re_exports` 9,
`extends` 5. Real call/import/inheritance structure is present (not just containment).

## Highest-connectivity nodes

| node | degree | note |
|---|---:|---|
| `agentrouter/cli.py` | 88 | Typer entrypoint; large surface — a **god-node candidate** (many commands in one file). |
| `EvaluationCase` | 82 | Shared eval DTO across adapters/runner/reports. |
| `classify()` | 67 | Core classifier; imported by cli, service, evaluate, tests. |
| `ModelEntry` | 59 | Registry model type, pervasive. |
| `plugins.py` / `install()` | 51 / 47 | Hardened plugin installer (TASK-008). |
| `agentrouter/schema.py` | 47 | Central schema hub. |

## Observations / hotspots

- **`cli.py` is the dominant hub** (degree 88). Expected for a CLI-first tool, but it concentrates
  route-control parsing, execution, eval, server/mcp launch. Candidate for later extraction if it
  keeps growing. Not a correctness issue.
- **`classify()` and `schema`/`ModelEntry` are the semantic core** — changes there ripple to cli,
  server/service, evaluate, and every eval adapter. Impact review mandatory before touching them.
- **Clean layering confirmed structurally**: `server/app.py` depends on `server/service.py`
  (not vice-versa); `mcp_server.py` reaches `service`, not the FastAPI app; `sdk/typescript` is a
  separate island (distinct-runtime client of the same `/v1` contract).
- `cli.py --imports_from--> safety.py` is a direct 1-hop edge — the safety gate is reached straight
  from the CLI execute path (matches the audited execution gating).

## Ambiguous / inferred edges (verify at source before trusting)

- `indirect_call` (30) and `references` (386) are heuristic. Treat as leads, not truth — open the
  cited `source_file:source_location`.
- 17 non-code files (JSON/config) produced zero nodes and are absent from the graph (expected).

## Known limitations

- Graph reflects the working tree at build time; rerun `graphify update .` after edits.
- TypeScript SDK nodes come from AST extraction of `sdk/typescript`; cross-language edges to the
  Python `/v1` contract are conceptual, not extracted.
- Community labels are AST/heuristic clusters, not authoritative architecture boundaries.
