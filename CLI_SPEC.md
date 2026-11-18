# AgentRouter OS — CLI Specification

> **Purpose:** Define every command, its arguments/flags, sample terminal I/O,
> and exit codes. The CLI (Typer) is a thin shell over the RoutingEngine
> ([ARCHITECTURE.md](ARCHITECTURE.md)). Command names here are canonical and
> match every other doc.
>
> Scope: `init`, `route`, `explain` (basic), `registry list`, `prompt generate`
> are **MVP**. `providers refresh` is **Capstone demo**. `feedback` is
> **Advanced**.

---

## 0. Global

- Binary: `agentrouter`
- Config + data home: `~/.agentrouter/`
  - `~/.agentrouter/config.yaml` — user settings (weights, default provider).
  - `~/.agentrouter/registry/models.yaml`, `providers.yaml` — the registries.
  - `~/.agentrouter/agentrouter.db` — SQLite decision + feedback log.
- Global flags: `--json` (machine output), `--config <path>`, `-v/--verbose`.

**Exit codes:** `0` success · `1` runtime error · `2` bad usage/args · `3`
registry validation failure · `4` no eligible model.

---

## 1. `init` — *MVP*

Scaffold `~/.agentrouter/` with default config and seed registries.

```
agentrouter init [--force]
```
- `--force` — overwrite existing config/registries.

```console
$ agentrouter init
Created ~/.agentrouter/config.yaml
Seeded registry/providers.yaml (6 providers)
Seeded registry/models.yaml (12 example models)
Initialized agentrouter.db
Ready. Try: agentrouter route "your task here"
```

---

## 2. `providers refresh` / `status` / `rollback` / `restore` / `doctor` — *Capstone demo*

`providers refresh` calls one live adapter (`openrouter`, `openai`) and writes its
catalog to `models.<provider>.generated.yaml`, next to the hand-edited
`models.yaml`. The manual registry always wins on key collision, so a refresh can
never shadow a hand-edited model. Every generated file carries a `provenance`
block (source URL, fetch time UTC, count, tool version, CLI args) that the
registry loader ignores; `status`/`doctor` read it back.

```
agentrouter providers refresh <provider> [--limit N] [--match SUBSTRING] [--dry-run]
agentrouter providers status
agentrouter providers rollback <provider>
agentrouter providers restore <provider>
agentrouter providers doctor
```
- `<provider>` — `openrouter` (public catalog) or `openai` (needs `OPENAI_API_KEY`).
- `--limit N` — cap how many models are imported (default 25).
- `--match SUBSTRING` — only import model ids containing this substring.
- `--dry-run` — print what would be imported; write nothing. If the provider
  already has a generated catalog, candidate deprecations (ids that were in the
  previous fetch but are missing from this one) are reported either way — never
  auto-deleted, the user decides.
- `status` — per-provider freshness (age vs. a 90-day staleness window) and, when
  present, the provenance source/fetch time; offline, reads only local files.
- `rollback <provider>` — back up (rotating any earlier `.bak`) then remove the
  generated file, reverting to the manual registry.
- `restore <provider>` — reverse the most recent `rollback`; refuses to clobber a
  generated file that was re-refreshed since.
- `doctor` — parse and schema-validate every generated catalog; exits non-zero
  only on real corruption (not merely staleness), with per-provider `[OK]`/`[FAIL]`
  lines.

```console
$ agentrouter providers refresh openrouter --limit 5
auth: no OPENROUTER_API_KEY set - using the public catalog endpoint
Fetched 5 models from openrouter:
  openrouter/vendor/frontier-x                        ctx    200000  frontier
  ...
Wrote registry/models.openrouter.generated.yaml
Manual models.yaml is untouched and wins on collision. Delete the .generated.yaml file to revert.
Next: agentrouter registry list

$ agentrouter providers status
openrouter      5 models  newest 2026-08-08 (0d)  fresh  source=https://openrouter.ai/api/v1/models

$ agentrouter providers doctor
[OK   ] openrouter      5 models  newest 2026-08-08 (0d)  fresh  source=https://openrouter.ai/api/v1/models
```

---

## 3. `route "<task>"` — *MVP*

Classify a task and produce a recommendation + fallback + prompt + checklist,
and log the decision. This is the core command.

```
agentrouter route "<task>" [--context-tokens N] [--risk low|medium|high]
                            [--tool file-edit,shell] [--json] [--no-log]
                            [--vendor V]... [--exclude-vendor V]... [--model V/ID]
                            [--host H]... [--exclude-host H]... [--max-price USD]
                            [--prefer-quality|--prefer-balanced|--prefer-cheap|--prefer-fast]
                            [--stable-only|--allow-preview]
                            [--available-only|--include-unavailable]
                            [--uncertainty-threshold F]
```
- `--context-tokens N` — override estimated context size.
- `--risk` / `--tool` — override classifier inference.
- `--no-log` — don't persist (skips `decision_id`).
- `--uncertainty-threshold F` — below this task-type confidence (0–1, default 0.4) the
  output flags the interpretation as low-confidence and suggests clarifying. The
  classification carries `confidence`, `needs_clarification`, `alternative_task_type`
  and `ambiguity_reason` (also in `--json`).

Route controls (Phase P3) filter the candidate pool before ranking:
- `--vendor` / `--exclude-vendor` — keep/drop by model maker (repeatable, case-insensitive).
- `--model V/ID` — pin to one model (`vendor/id`, `provider/id`, or bare `id`).
- `--host` / `--exclude-host` — keep/drop models runnable on given execution hosts.
- `--max-price USD` — cap input price per 1M tokens. Models with **unknown** price are
  excluded (never fabricated); until catalogs carry real prices this excludes all seeds.
- `--stable-only` — only stable-channel models; mutually exclusive with `--allow-preview`.
- `--available-only` — only models with an available host; excl. with `--include-unavailable`.
- `--prefer-quality|cheap|fast|balanced` — fixed weight vector that overrides the
  complexity/context weight shifts (at most one). Reflected in `weight_shifts`.

Filter-excluded models appear in the JSON `excluded` list with a `control:` reason.
An impossible filter set exits `4` (no eligible model); conflicting flags exit `2`.

```console
$ agentrouter route "Refactor auth to use JWT rotation and add tests"

Classification
  task_type coding · complexity high · risk high · context medium(~12k)
  output code+tests · tools file-edit,shell · approval human-approval-required

Recommendation                                        score
  1  claude-code / <frontier-coding-model>            0.91   ← recommended
  2  cursor      / <strong-coding-model>              0.84   ← fallback

Safety checklist (risk=high)
  [ ] Review full diff before applying
  [ ] Run the test suite
  [ ] Secret scan changed files
  [ ] Confirm rollback path
  [ ] Human sign-off (no auto-execute)

Execution prompt saved. Decision id: d_00042
Next: agentrouter explain d_00042
```

Exit `4` if no model is eligible (recommends manual-agent, still logs).

---

## 4. `explain <decision_id>` — *MVP (basic) / Capstone (rich)*

Reconstruct a logged decision: classification, eligibility, full score table.

```
agentrouter explain <decision_id> [--json]
```

```console
$ agentrouter explain d_00042
Task: "Refactor auth to use JWT rotation and add tests"
Classification: coding/high/high/medium · tools[file-edit,shell]

Eligibility: 12 models → 5 eligible (7 excluded: 4 no file-edit, 3 context<12k)

Scores (top 5)
  model                                cap  cost  lat  ctx  adj   score
  <frontier-coding-model>              0.95 0.60 0.70 0.90 +0.05  0.91  ✔ recommended
  <strong-coding-model>                0.85 0.75 0.80 0.85 +0.05  0.84  ✔ fallback
  <mid-tier-coding-model>              0.70 0.90 0.90 0.80  0.00  0.78
  ...
Weights: cap .55 cost .15 lat .15 ctx .15 (shifted: complexity=high)
Gate: risk=high → human-approval-required, auto-execute blocked
```

---

## 5. `feedback <decision_id>` — *Advanced*

Record an outcome; the learning loop nudges weights.

```
agentrouter feedback <decision_id> --rating 1-5 [--accepted|--overrode <model>] [--note "..."]
```

```console
$ agentrouter feedback d_00042 --rating 5 --accepted --note "worked, tests passed"
Recorded. Acceptance rate: 83% (39/47). Weights nudged: w_cap +0.01
```

---

## 6. `registry list` — *MVP*

Print loaded models with key attributes.

```
agentrouter registry list [--provider <id>] [--active-only] [--json]
```

```console
$ agentrouter registry list --provider openrouter --active-only
PROVIDER    MODEL_ID                 CTX     PRICE     LAT   CODE/REAS/WRITE  TOOLS
openrouter  <mid-tier-coding-model>  128000  low       fast  7/7/7            tool-use,fn
openrouter  <cheap-fast-model>       32000   free      fast  5/6/6            fn
...
```

---

## 7. `prompt generate` — *MVP*

Generate (or regenerate) an execution prompt for a task or a logged decision,
without routing.

```
agentrouter prompt generate ["<task>" | --from <decision_id>] [--tool <id>] [--out <file>]
```

```console
$ agentrouter prompt generate --from d_00042 --out prompt.md
Wrote execution prompt for claude-code/<frontier-coding-model> → prompt.md
```

---

## 7b. `plugin` — host integrations (Phase P8)

Install AgentRouter's host integrations from bundled package data.

```
agentrouter plugin list
agentrouter plugin install <name> [--dry-run] [--force]
agentrouter plugin uninstall <name>
agentrouter plugin doctor [--json]
```
- Plugins: `claude-code` (skill → `~/.claude/skills/agentrouter/SKILL.md`),
  `codex` (`~/.codex/AGENTS.md`).
- **Idempotent** (identical dest is skipped), **reversible** (a differing user file is
  backed up to `<file>.agentrouter-bak` and restored on uninstall), **safe** (never
  overwrites a differing user file without `--force`).
- `--dry-run` prints the exact files and actions without changing anything.
- `doctor` **diagnoses** rather than describes: for every destination it reports
  the state and the exact safe fix. Exit `0` installed and unmodified, `1` blocked
  (a destination AgentRouter refuses to write through, or an unreadable ownership
  record), `2` needs attention. `--json` for scripts.
  - It distinguishes an **identical** pre-existing copy (byte-for-byte ours, safe
    to adopt with `--adopt-identical`) from a **different** file at that path,
    which is never assumed to be ours.
  - A blocked destination is never given a "delete it" remedy; the judgement is
    left to whoever can see what the link points at.
  - It never prints file contents — the output is meant to be pasteable into a
    support request.
- Plugin state also appears in unified `agentrouter doctor` as `plugins.state`.
- Set `AGENTROUTER_PLUGIN_ROOT` to install under a custom base (used by tests).
- Unknown plugin → exit `2`.
- Safety guarantees, and the Windows behaviour that is **not** guaranteed, are in
  `SECURITY.md` and `KNOWN_LIMITATIONS.md`.

---

## 8. Command → tier summary

| Command | Tier |
|---|---|
| `init` | MVP |
| `route` | MVP |
| `explain` | MVP (basic), Capstone (rich table) |
| `registry list` | MVP |
| `prompt generate` | MVP |
| `providers refresh/status/rollback/restore/doctor` | Capstone demo |
| `feedback` | Advanced |
