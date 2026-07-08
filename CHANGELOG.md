# Changelog

All notable changes to AgentRouter OS. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [Unreleased]

## [0.2.0] - 2026-07-08

### Added
- **Live `providers refresh openrouter`** (Capstone M2): fetches the OpenRouter
  catalog into `registry/models.openrouter.generated.yaml`; manual registry
  always wins on collision; `--limit`, `--dry-run`; keyless operation
- GitHub Actions CI (Python 3.11/3.12/3.13): ruff lint + format check,
  pytest with 80% coverage gate, CLI entrypoint smoke check
- Dev tooling: ruff config, pytest-cov, `[dev]` extras in pyproject
- CLI smoke tests; contributor docs (CONTRIBUTING.md, TESTING.md, SECURITY.md,
  RELEASE.md)

### Changed
- Codebase formatted and linted with ruff (no behavior changes)
- pyproject.toml: full package metadata (license, classifiers, URLs)

## [0.1.0] - 2026-07-07

### Added
- Production-grade local CLI MVP: `init`, `route`, `explain`, `feedback`,
  `registry list`, `prompt generate`, `--json` output
- Rule-based 7-dimension task classifier with documentation-intent priority
  and CLI overrides
- Pydantic-validated YAML model/provider registries; hard eligibility filters
- Weighted scoring engine with recommendation + fallback and plain-English reason
- Risk-scaled safety gates; high-risk tasks require human approval
- SQLite decision log with replayable `explain`
- 46 offline tests; what/why/next error handling
