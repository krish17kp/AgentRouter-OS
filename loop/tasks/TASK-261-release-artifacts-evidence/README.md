# TASK-261 — Release artifact evidence

## Evidence

- Isolated PEP 517 build produced `agentrouter_os-0.5.0rc1` wheel and sdist.
- Wheel contains the package and `context_band_model_v1.json`; archive
  inspection found no required packaged asset missing.
- `twine check` passes for both artifacts in an isolated tool environment.
- Website `npm run lint` and `npm run build` pass.
- `cargo audit --no-yanked` reports no vulnerability advisories across 207
  locked dependencies; the only warning is the documented unmaintained
  `chrono` crate with no fixed upgrade.

These are release-readiness artifacts only. The context-band gate, human
review, promotion approval, credentials, and deployment remain unresolved.
