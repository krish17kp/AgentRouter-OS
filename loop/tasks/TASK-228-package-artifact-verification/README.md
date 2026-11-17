# TASK-228 — Package artifact verification

## Objective

Rebuild and validate the release sdist and wheel from the current checkout.

## Acceptance

- both artifacts build successfully;
- `twine check` passes for both artifacts;
- existing packaging warnings remain visible and are not mistaken for a
  release-gate pass.
