# TASK-234 Evidence

Date: 2026-11-18

## Verification

Rebuilt the current source with `uv build`; the captured log contains no
`DeprecationWarning` or `deprecated` lines. Both artifacts pass `twine check`:

```text
Successfully built dist/agentrouter_os-0.5.0rc1.tar.gz
Successfully built dist/agentrouter_os-0.5.0rc1-py3-none-any.whl
Checking dist/agentrouter_os-0.5.0rc1-py3-none-any.whl: PASSED
Checking dist/agentrouter_os-0.5.0rc1.tar.gz: PASSED
```

The wheel was installed into a fresh temporary environment outside the source
checkout. It reported `agentrouter-os 0.5.0rc1`, exposed
`python -m agentrouter.reliability --help`, initialized a new home, and routed
`summarize a support ticket` locally with a recommendation and no provider
request.
