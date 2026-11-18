# Repair loop — TASK-007

Self-caught before audit: SBOM step used `--outfile` (unrecognized) -> fixed to
`--output-file` (verified via --help + a live run producing valid CycloneDX). No audit
findings required repair. The CHANGELOG/pyproject Python-floor drift is pre-existing and
out of scope; recorded as an owner follow-up, not fixed (compatibility decision).
