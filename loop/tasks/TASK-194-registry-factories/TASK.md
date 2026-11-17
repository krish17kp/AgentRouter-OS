# TASK-194 — Registry callable factory parity

## Objective

Match the Python registry's `available_adapters()` callable-factory surface in
Rust while retaining cheap descriptor-only discovery.

## Acceptance

- Rust exposes lazy callable factories for every registered adapter;
- each factory constructs the concrete adapter facade and preserves registry
  ordering;
- focused Rust tests, workspace checks, and compatibility tests pass;
- external real-data loading remains explicitly blocked and documented.
