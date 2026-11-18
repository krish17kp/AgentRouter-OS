# Release check — TASK-007

| AC | Status | Evidence |
|----|--------|----------|
| release workflow generates + attaches CycloneDX SBOM | PASS | release.yml step; cmd proven (127-component CycloneDX) |
| workflow attests SLSA provenance (OIDC, no secret) | PASS | actions/attest-build-provenance@v1; minimal perms |
| SBOM cmd proven locally; [sbom] extra declared | PASS | cyclonedx-py env run; pyproject [sbom] |
| UPGRADING.md documents versioning + migration | PASS | verified accurate vs cli.py |
| no Python behavior change; suite green | PASS | 426 passed |

**Verdict: PASS.** Only-remaining-local-backlog item complete. Product remains
BLOCKED_EXTERNAL (P1/P2/P5/P11/P13-15). A §10 product audit is now due (7 tasks completed).
