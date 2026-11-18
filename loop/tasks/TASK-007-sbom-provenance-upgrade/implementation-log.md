# Implementation log — TASK-007

## Files changed
- .github/workflows/release.yml: SBOM generation + gh release upload + SLSA attestation
  (build job perms: contents/id-token/attestations: write); dist + sbom as separate artifacts.
- pyproject.toml: `[sbom]` extra (cyclonedx-bom>=4.0).
- NEW UPGRADING.md (versioning + upgrade + migration + downgrade + supply-chain verify).
- RELEASE.md: supply-chain (SBOM + provenance) section.
- .gitignore: *.cdx.json, sbom.json (generated at release/CI, not committed).

## Decisions (ponytail)
- No committed SBOM (goes stale) -> generated at release time; command proven locally.
- Provenance via official GitHub attestation action (OIDC, no stored secret).
- Separate `sbom` artifact so publish job's dist/ stays PyPI-clean.

## Self-caught bug: used --outfile (unrecognized) -> fixed to --output-file (proven -o).
## Verify: workflows valid YAML; SBOM cmd -> 127-component CycloneDX JSON; pytest 426.
