# Customer review — TASK-005

- S3 (integrator): `pip install "agentrouter-os[mcp]"` + `agentrouter mcp` serves over stdio;
  README documents the mcpServers registration JSON. Tools are read/route/explain (no execute).
- After the repair, [mcp] is genuinely self-sufficient (no hidden fastapi requirement). PASS.
- Note: `agentrouter mcp --help` shows `pip install "agentrouter-os"` (Typer strips the
  bracket) — pre-existing cosmetic issue; README has the correct command. Follow-up.
