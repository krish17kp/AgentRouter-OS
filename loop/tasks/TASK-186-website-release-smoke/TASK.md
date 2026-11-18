# TASK-186 — Website release smoke

## Objective

Refresh the website release evidence from the current checkout: lint the
frontend, build the production bundle, and audit runtime dependencies.

## Acceptance

- `npm run lint` passes with zero warnings;
- `npm run build` produces the Vite production bundle;
- `npm audit --omit=dev --audit-level=high` reports no production
  vulnerabilities.

## Non-goals

This does not publish or deploy the site; hosting credentials and production
promotion remain owner-controlled gates.
