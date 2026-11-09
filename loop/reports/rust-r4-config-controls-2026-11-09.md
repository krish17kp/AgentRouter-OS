# Rust R4 configured routing and controls — 2026-11-09

## Scope

- The Rust route probe loads scoring weights, feedback-learning switch, and
  pricing policy from `config.yaml`.
- It applies hard route controls before scoring, retaining exclusion reasons.
- Rust host discovery checks the user's home for CLI credentials even when
  `AGENTROUTER_HOME` relocates AgentRouter data.
- Independent review found two fail-open edge cases. The Rust and Python
  route CLI now reject non-finite or negative price caps; direct Python and
  Rust control application also cannot admit a model under such a cap. Rust
  never looks in the current directory for CLI credentials when home
  environment variables are unavailable.
- Python remains the shipping implementation. This probe does not provide
  public Rust CLI, HTTP, MCP, or live provider execution parity.

## Verification

- `uv run --no-sync pytest -q`: 1,336 passed, 3 skipped, 1 warning after
  the independent-review repairs.
- `cargo +1.75.0 test --workspace --locked`: pass.
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`: pass.
- `cargo fmt --all --check`: pass.
- `uv run --no-sync ruff check .` and `ruff format --check .`: pass.
- Bandit, pip-audit (`requirements.txt`), and wheel/sdist build: pass.
- Fresh wheel install with `[server,mcp]` outside the repository: `init`,
  JSON route, package import, API import, and MCP import pass.
- `git diff --check`: pass.
- Differential cases cover configured routes, learning switch, controls,
  no-eligible results, malformed config, unknown controls, invalid price caps,
  and home lookup. Focused review-repair tests: 61 passed.
- Prior pushed commit `3281c41` passed GitHub checks. Later workflow runs
  on `0ac4335` and `e8bbc58` failed before jobs began due to GitHub internal
  server errors, so the new head still needs remote verification.

## Release status

The canonical evaluation is 6/7 gates, with context-band accuracy 0.6667
below the unchanged 0.90 threshold. The two-human annotation/adjudication
round in `TASK_012_OWNER_ACTIONS.md` remains external. No AI-generated label
was used as a human label; no paid provider call was made.
