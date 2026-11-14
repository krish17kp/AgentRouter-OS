# Plan — TASK-007 SBOM + provenance + upgrade guide (L7)

## Design (ponytail, reuse existing release flow)
- Extend .github/workflows/release.yml build job: generate CycloneDX SBOM
  (cyclonedx-py environment), attach to the Release (gh release upload), attest SLSA
  provenance (actions/attest-build-provenance@v1, OIDC). Upload dist + sbom as SEPARATE
  artifacts so the publish job's dist/ stays clean.
- pyproject `[sbom]` extra (cyclonedx-bom).
- UPGRADING.md: SemVer policy, upgrade steps, config/registry migration (init --force),
  downgrade, supply-chain verify (gh attestation verify).
- RELEASE.md supply-chain section; .gitignore *.cdx.json.

## Verify (locally verifiable parts)
YAML validity of all workflows; SBOM command produces valid CycloneDX JSON; python suite
unaffected. (The workflow itself runs in CI — like the other workflows, not run locally.)

## Risk: low (docs + CI config; no Python behavior change).
