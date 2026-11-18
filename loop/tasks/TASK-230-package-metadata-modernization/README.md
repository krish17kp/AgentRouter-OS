# TASK-230 — Package metadata modernization

## Objective

Remove the setuptools license-metadata deprecation warnings from the release
build while preserving the distribution name, version, license, and runtime
package contents.

## Acceptance

- `uv build` completes without license-metadata deprecation warnings;
- `uvx twine check` passes for the sdist and wheel;
- the package-version compatibility test remains green.
