# Deployment plan

This plan describes the production path without pretending that staging or
deployment has happened. Python remains the shipping authority until the Rust
retirement criteria in [`RUST_MIGRATION_PLAN.md`](../RUST_MIGRATION_PLAN.md)
are satisfied; the Rust binaries are validated as compatibility artifacts, not
as an unapproved cutover.

## Release boundary

```text
frozen evaluation + human review
            │
            ▼
hosted CI + offline release gates ──► immutable tag
            │                              │
            ▼                              ▼
       staging smoke ───────────────► canary production
                                           │
                                           ▼
                                      full promotion
```

The release workflow builds the Python sdist/wheel, runs the offline release
gate, creates the CycloneDX SBOM, emits SLSA provenance, attaches the SBOM to
the GitHub Release, and publishes through PyPI Trusted Publishing. A service
deployment is a separate owner-approved operation; publishing a package or
website does not prove that an API service is deployed.

## Preconditions

- The frozen context-band gate is at least `0.90`, with the required human
  annotator/adjudicator evidence recorded. AI-generated labels do not satisfy
  this gate.
- PR review is complete and all required hosted checks are green, including
  security, mutation, Python/Rust compatibility, website, and release-readiness
  checks. A skipped live smoke must be resolved with an authorized provider
  credential before production promotion.
- The owner has supplied the deployment target, domain/DNS control, secret
  manager, provider budget/credential, and explicit promotion approval.
- The exact release commit is tagged and the working tree is clean. Record the
  tag, image/package digests, database schema version, and configuration
  revision in the release evidence.

## Staging runbook

1. Build from the immutable release tag using the same artifact workflow as
   production. Verify the wheel/sdist hashes, SBOM, provenance, and Rust
   release binaries if they are included in the staged bundle.
2. Provision an isolated staging home and database. Never copy production
   credentials or decision-log contents into staging; use a dedicated provider
   key with a bounded budget.
3. Start the service with production-like limits and observability settings.
   Verify `/health`, `/ready`, the committed OpenAPI contract, request IDs,
   authentication, rate limits, idempotency, diagnostics, and the Rust/Python
   compatibility smoke suite.
4. Run the bounded reliability load and soak profiles. Record correctness
   errors, transport errors, resource samples, p50/p95/p99 timings, and the
   exact workload. Timing is evidence, not an invented gate.
5. Exercise the rollback procedure against staging before any production
   promotion. Preserve the generated bundle, logs, SBOM, and test report as
   release evidence.

## Production promotion

- Promote the same immutable artifact, configuration revision, and schema
  migration tested in staging; do not rebuild from a moving branch.
- Start with a canary slice and observe health, error rate, latency, provider
  spend, database growth, request-ID correlation, and diagnostic redaction.
- Expand traffic only after the canary window is explicitly approved. Keep the
  previous artifact available until the owner signs off on the promotion.
- Publish the GitHub Release/PyPI package only after the release workflow's
  offline gate and the service canary are both green. Website publication is
  independently verified by its website workflow.

## Rollback

1. Stop promotion and route traffic to the last approved artifact.
2. Revert the service/package pointer to the previous immutable digest; do not
   delete the failed release or overwrite its evidence.
3. If a schema migration was applied, use a reviewed backward-compatible
   migration or restore the pre-deploy snapshot only under owner approval.
   Never restore a decision log from an unverified filesystem copy.
4. Re-run `/health`, `/ready`, contract, authentication, rate-limit, and
   decision-log integrity checks before reopening traffic.
5. Attach the incident timeline, failed bundle, rollback command/output, and
   final artifact digests to the release record. A rollback drill is not
   considered complete until it has actually been exercised in staging.

## Current state

No staging or production deployment has been performed from this checkout. The
current release candidate is therefore **not production-ready**: the frozen
human evaluation gate, authorized live-provider validation, hosted promotion,
and deployment credentials/approval remain open.
