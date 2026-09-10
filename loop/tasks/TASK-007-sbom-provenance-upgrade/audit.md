# Independent audit — TASK-007

## verification-engineer — all 5 items PASS
- All 3 workflows valid YAML.
- SBOM command reproduced (module + console-script forms): CycloneDX 1.6, 127 components;
  --output-file is the correct flag (not --outfile).
- release.yml: dist/ stays clean for PyPI (SBOM is a SEPARATE artifact); permissions minimal
  and correct (contents/id-token/attestations: write); `github.event.release.tag_name` is the
  right context for a release:published trigger.
- python suite 426 (unaffected).
- UPGRADING.md claims cross-checked against cli.py (init --force reseeds; AGENTROUTER_HOME;
  agentrouter.db) — accurate.

## Notes (non-blocking)
- Optional: pin third-party actions to SHA (consistency) — deferred; existing workflow uses
  version tags too, so pinning only new steps would be inconsistent.
- PRE-EXISTING, OUT OF SCOPE: CHANGELOG [Unreleased] says Python floor is 3.11, but
  pyproject requires-python>=3.10 + CI matrix includes 3.10. Compatibility policy decision
  -> flagged for owner in KNOWN_LIMITATIONS; NOT changed (would be a guessed product decision).
