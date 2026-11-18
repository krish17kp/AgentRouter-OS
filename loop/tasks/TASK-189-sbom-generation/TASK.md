# TASK-189 — Release SBOM generation

## Objective

Exercise the release workflow's local CycloneDX SBOM generation path and
verify that the packaged environment produces a valid component inventory.

## Acceptance

- the SBOM tool runs from the declared optional dependency set;
- output is valid CycloneDX JSON;
- the component count is recorded;
- the generated artifact remains outside the repository unless explicitly
  attached to a release.
