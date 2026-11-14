# Codex takeover baseline - 2026-07-20

Repository: `D:\Krish\Agentrouteros`
Initial branch/HEAD: `main` / `602321af91ff298c0d5b59d6d36c24f845557fc1`
Remote: `https://github.com/krish17kp/AgentRouter-OS.git`

This baseline was captured before changing production behavior. It independently tests the
uncommitted working tree inherited from prior sessions; no completion flag was trusted.

| Check | Result |
|---|---|
| `python -m pytest -q` | PASS - 427 passed; one Starlette/httpx deprecation warning |
| hook tests | PASS - 15 passed |
| `ruff check .` | PASS |
| `ruff format --check .` | FAIL - 3 inherited `.claude/hooks` files need formatting |
| Bandit | PASS - zero findings; five justified exclusions |
| pip-audit | PASS - no known vulnerabilities |
| `agentrouter eval run --all` | PASS - 98.32/100, 165 cases, 7/7 gates |
| TypeScript `npm ci && npm test` | PASS - 8/8 |
| TypeScript typecheck | PASS |
| wheel + sdist build | PASS - 0.4.0 artifacts; future setuptools license warnings |
| clean-wheel acceptance | PASS - fresh venv and non-repository cwd |

## Clean-wheel details

Installed `dist/agentrouter_os-0.4.0-py3-none-any.whl[server,mcp]` into a fresh Python 3.13
environment. From outside the repository, verified package import and metadata version 0.4.0;
`agentrouter --help`, `init`, `setup`, `registry list`, `hosts list`, `route`,
`eval list-datasets`, and `eval run --all`; packaged benchmark, seven fixtures, and plugin payloads;
and API/MCP imports. Evaluation reproduced 98.32/100 and all seven mandatory local gates.

Evidence temp root:
`C:\Users\krish\AppData\Local\Temp\agentrouter-codex-wheel-984c6723ae73494984c5575dd3533ae6`.

## Baseline defects / warnings

1. Repository-wide format gate fails on three `.claude/hooks` files.
2. TASK-008 and TASK-009 are locally actionable despite stale durable state claiming the local
   backlog is exhausted.
3. No Linux mutation workflow or valid mutation score exists yet.
4. Build succeeds but setuptools warns the TOML license table/classifier metadata will require a
   future migration.

