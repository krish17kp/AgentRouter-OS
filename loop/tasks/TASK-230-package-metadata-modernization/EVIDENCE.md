# TASK-230 Evidence

Date: 2026-11-18

## Verification

Updated `pyproject.toml` to use the modern SPDX license string and removed the
redundant license classifier. Rebuilt the release artifacts with `uv build`.
The captured build log contains no `DeprecationWarning` or `deprecated` lines.

```text
Successfully built dist/agentrouter_os-0.5.0rc1.tar.gz
Successfully built dist/agentrouter_os-0.5.0rc1-py3-none-any.whl
Checking dist/agentrouter_os-0.5.0rc1-py3-none-any.whl: PASSED
Checking dist/agentrouter_os-0.5.0rc1.tar.gz: PASSED
```

The package-version compatibility test was also rerun after the metadata-only
change:

```text
1 passed
```
