# TASK-231 — Local SBOM verification

## Objective

Exercise the release workflow's CycloneDX generation locally against the
candidate environment and verify that the installed distribution is present in
the resulting component inventory.

## Acceptance

- generate a CycloneDX JSON SBOM using the release command;
- confirm the candidate distribution and version appear in the inventory;
- keep publication and provenance attestation owner-controlled.
