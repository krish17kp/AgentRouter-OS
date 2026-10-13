# Repair loop — TASK-004

Iteration 1 (self-caught during measurement): first signal set regressed typ-006 ("debug"
too broad) and sum-012 (gate removed its bump). Dropped debug/diagnose/troubleshoot/upgrade;
added "documentation". -> 0.945.

Iteration 2 (from product-architect audit): "documentation" is a writing noun that
over-triggers on greenfield "write documentation" prompts (fixture-motivated). Removed it;
instead added TaskType.summarization to the M_EXISTING_CODE gate so "Summarize the API
documentation" stays medium via a principled path (summarize + existing component).
Re-verify: context_band 0.945 (unchanged), sum-012 medium, all 7 gates PASS, 418 tests.
