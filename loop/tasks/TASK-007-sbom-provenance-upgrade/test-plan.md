# Test-first contract — TASK-007

- release.yml/ci.yml/security.yml parse as valid YAML.
- `cyclonedx-py environment --output-format JSON --output-file X` -> valid CycloneDX
  (bomFormat CycloneDX, non-empty components). Correct flag is --output-file, not --outfile.
- publish job's dist artifact excludes the SBOM (clean PyPI upload).
- UPGRADING.md claims match repo (init --force reseeds; AGENTROUTER_HOME; agentrouter.db).
- python `pytest -q` stays 426.
