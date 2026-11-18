# Rust provider refresh mapping

`agentrouter-registry::refresh` ports the deterministic conversion slice from
`agentrouter/refresh.py`. It maps OpenRouter pricing and capabilities, maps
OpenAI model IDs through the static family table, and applies offline payload
limits, substring filters, and warning rules. No provider credentials or
network access are needed for these operations.

## Compatibility checks

`tests/test_rust_refresh_compat.py` compares complete JSON model records with
the Python `ModelEntry` output. Coverage includes all current OpenAI family
prefixes, overlapping prefix selection, OpenRouter pricing tiers, tool and
vision metadata, default output sizes, catalog limits, and malformed rows.
Dates are supplied explicitly to both implementations so the fixtures remain
deterministic.

This is a Rust migration slice, not a replacement for
`agentrouter providers refresh`. Live HTTPS retrieval, API-key handling,
generated-file provenance, atomic writes, previous-catalog deprecation
reporting, and CLI behavior remain Python responsibilities.
