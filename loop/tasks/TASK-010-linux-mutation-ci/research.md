# TASK-010 research

- Mutmut 3.6.0 uses `[tool.mutmut]`, `source_paths`, `only_mutate`, and
  `pytest_add_cli_args_test_selection`; its generated `*.py.meta` files contain
  per-mutant exit codes.
- Mutmut 3 requires Linux process-fork behavior for this campaign, so Windows local
  execution is intentionally rejected and GitHub Ubuntu is authoritative.
- GitHub Actions supports job-level `timeout-minutes`, conditional artifact upload,
  and nonzero step failure. The wrapper adds a shorter subprocess timeout so reports
  are written before the job-level deadline.
- Score definition is explicit in every report: killed, timeout, and type-check-caught
  mutants divided by those outcomes plus survivors. Incomplete outcomes never enter a
  passing denominator.
