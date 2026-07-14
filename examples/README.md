# AgentRouter OS — examples

Every command here runs offline against the seeded catalog (`agentrouter init`
or `agentrouter setup` first). Nothing leaves your machine.

## 1. First run (onboarding)

```console
$ agentrouter setup --preference balanced
# seeds ~/.agentrouter, lists execution hosts, saves a preference,
# routes one sample task, and prints how to install a host integration.
```

## 2. Coding-agent routing

```console
$ agentrouter route "refactor the payment module and add unit tests"
# -> a frontier coding model; risk=high => execution is gated (no auto-run).
```

## 3. Low-cost batch routing

```console
$ agentrouter route "reformat this JSON and fix the indentation" --prefer-cheap
# cost weighted up => cheapest adequate tier instead of a frontier model.
```

## 4. Quality-first routing

```console
$ agentrouter route "design a multi-region failover architecture" --prefer-quality
```

## 5. Vendor / host / policy constraints

```console
$ agentrouter route "summarize this PDF" --vendor anthropic --available-only
$ agentrouter route "write a shell script" --prohibit-tool shell   # exclude shell-capable models
$ agentrouter route "build a scraper" --stable-only --max-price 5   # stable channel, price cap
```

## 6. Ambiguous tasks (confidence & abstention)

```console
$ agentrouter route "do it"
# confidence: 0.00  ->  "Low confidence ... consider clarifying"; still shows a best guess.
$ agentrouter route "do it" --uncertainty-threshold 0.2   # tune how eager it is to flag
```

## 7. Local, private routing

All routing is local and rule-based; `--no-log` skips persistence, `--json`
gives machine output for scripting:

```console
$ agentrouter route "classify these support tickets" --no-log --json
```

## 8. Install into Claude Code / Codex

```console
$ agentrouter plugin install claude-code    # ~/.claude/skills/agentrouter/
$ agentrouter plugin install codex          # ~/.codex/AGENTS.md
$ agentrouter plugin doctor                 # show status + exact paths
$ agentrouter plugin uninstall claude-code  # reversible; restores any backup
```

See `CLI_SPEC.md` for the full flag reference.
