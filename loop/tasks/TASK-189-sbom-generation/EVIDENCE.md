# TASK-189 evidence

Date: 2026-11-17

```console
uv run --with '.[sbom]' cyclonedx-py environment \
  --output-format JSON --output-file /tmp/agentrouter-sbom-2026-11-17.json
```

The command passed. The generated document is CycloneDX 1.6 JSON with 46
components. The artifact was written to `/tmp` and was not added to the
repository; the release workflow remains responsible for attaching its SBOM
to an approved GitHub Release.
