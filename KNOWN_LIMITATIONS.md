# Known Limitations

## Route controls (Phase P3)
- `--max-price` excludes every seed model today because seeds carry no
  `input_price_per_million`. It filters correctly once real prices land (P1). This is
  deliberate: unpriced models are never assumed under-budget (see AD-3).
- `--privacy local-only` and `--max-estimated-cost` from the spec are not implemented;
  routing is already local-only and cost estimation is not yet wired.

## Still blocked on external inputs (unchanged this loop)
- P1 dynamic catalog refresh for anthropic/openai/google/openrouter — needs live
  authenticated APIs + a large mocked-test surface.
- P2 host *access* verification (live network) — env-var/PATH presence only today.
- P5 measured model profiles — ability scores are curated guesses (`ability_source:
  curated`), not benchmark-measured.

## Local environment note
- The developer's `~/.agentrouter/registry/models.yaml` predates the real catalog and
  still holds placeholder IDs (`frontier-coding-model`, …). Run `agentrouter init --force`
  to re-seed with the real anthropic/openai catalog. Repo seeds are correct.
