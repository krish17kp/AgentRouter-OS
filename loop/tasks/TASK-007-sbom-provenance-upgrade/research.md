# Discover — TASK-007
- RELEASE.md: git-tag + GitHub Release flow; release.yml builds sdist+wheel and publishes
  to PyPI via Trusted Publishing (OIDC, no token). SemVer; CHANGELOG [Unreleased].
- No SBOM or provenance today. AGENTROUTER_HOME config/registry migration is via
  `agentrouter init --force` (per KNOWN_LIMITATIONS).
- cyclonedx-bom (`cyclonedx_py environment`) proven locally -> valid CycloneDX JSON.
- Provenance: GitHub `actions/attest-build-provenance@v1` (OIDC, credential-free).
