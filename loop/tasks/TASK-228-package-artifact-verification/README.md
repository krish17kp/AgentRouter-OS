# TASK-228 — Package artifact verification

## Objective

Rebuild and validate the release sdist and wheel from the current checkout.

## Acceptance

- both artifacts build successfully;
- `twine check` passes for both artifacts;
- packaging warnings are recorded accurately; follow-up cleanup is tracked in
  TASK-230.
