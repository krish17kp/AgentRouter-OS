# TASK-192 evidence

Date: 2026-11-17

```console
uv run --with '.[dev,server,security]' pytest -q
```

Result: **2,735 passed, 7 skipped, 1 warning in 449.37s (7m29s)**.

The warning is the existing Starlette deprecation notice recommending
`httpx2`; no test or frozen evaluation data was changed.
