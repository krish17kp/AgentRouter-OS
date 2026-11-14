# TASK-143 — runtime Rust CLI surface in evaluation

## Objective

Make the Rust seven-dimension evaluation score the command and group surface of
the Rust CLI that is installed and executed with it.

## Scope

- Expose a private JSON manifest command from the Rust `agentrouter` binary.
- Have `agentrouter-evaluate run --all` read the manifest from its sibling CLI.
- Fail with a clear error if runtime surface discovery is unavailable or invalid.
- Verify the report uses the discovered command and group lists.

## Acceptance

- The full evaluation scorecard discovers the actual sibling CLI surface.
- The Rust platform score and detail reflect that manifest.
- The compatibility test confirms the command set matches the current Python
  platform contract and accounts for the hidden Python-only `contract` group.
