# TASK-187 — Package build and installed-wheel smoke

## Objective

Verify that the Python release artifacts can be built and used from an
isolated environment, including packaged seeds, fixtures, and the CLI entry
point.

## Acceptance

- source distribution and wheel build successfully;
- an isolated install reports the candidate version;
- installed-wheel `init` and `route --json` succeed with a fresh home;
- no publication or external release mutation is performed.
