# TASK-231 Evidence

Date: 2026-11-18

## Verification

Installed the release workflow's `cyclonedx-bom` dependency into the isolated
local environment and ran:

```text
cyclonedx-py environment --output-format JSON --output-file /tmp/agentrouter-sbom.cdx.json
```

The generated document is CycloneDX 1.6 with 59 components. It contains the
candidate distribution as `agentrouter-os==0.5.0rc1`, declares the MIT license,
and identifies the checkout as the local package source. GitHub release asset
attachment and SLSA provenance attestation remain workflow/owner-controlled.
