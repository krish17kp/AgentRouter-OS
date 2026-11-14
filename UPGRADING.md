# Upgrading AgentRouter OS

AgentRouter OS follows [SemVer](https://semver.org): `MAJOR.MINOR.PATCH`.

- **PATCH** — bug fixes, no behavior change. Upgrade freely.
- **MINOR** — additive features, backward compatible (new flags, new endpoints,
  new optional extras). Existing commands, CLI output shape, and the `/v1` API
  contract keep working.
- **MAJOR** — a breaking change. See the version's `CHANGELOG.md` entry and the
  matching section below before upgrading.

## Upgrade steps

> **Not published to PyPI yet.** Until the first PyPI release, install and upgrade
> from source (`git clone … && pip install -e .`). The `pip install --upgrade
> agentrouter-os` commands below apply once the package is published.

```console
# 1. Upgrade the package (once on PyPI; until then: git pull && pip install -e .)
pip install --upgrade agentrouter-os

# 2. Confirm the CLI still starts and the version is what you expect
agentrouter --help
python -m agentrouter --help

# 3. Re-run your own smoke check
agentrouter route "summarize this PR"
```

Optional extras are versioned with the core package; re-install the ones you use:

```console
pip install --upgrade "agentrouter-os[server,mcp]"
```

## Config & registry migration

All state lives under `AGENTROUTER_HOME` (default `~/.agentrouter/`): `config.yaml`,
`registry/*.yaml`, and `agentrouter.db` (the decision log).

- **Config / registry schema changes** are called out in `CHANGELOG.md`. To adopt
  new seed defaults after a MINOR/MAJOR upgrade, re-seed:

  ```console
  agentrouter init --force     # rewrites seed registries; your edits to models.yaml are replaced
  ```

  `init --force` now backs up each seed file it overwrites (`config.yaml`,
  `registry/providers.yaml`, `registry/models.yaml`) to a `.bak` sibling before
  reseeding, so a hand-edited catalog can be recovered from e.g.
  `registry/models.yaml.bak`.

- **Decision log (`agentrouter.db`)** is backward compatible within a MAJOR line;
  new columns are additive. A MAJOR upgrade that changes the schema will document a
  migration (or say the log can be safely deleted — it is a local cache, not source
  of truth).

## Downgrade / rollback

```console
pip install "agentrouter-os==<previous-version>"
```

The decision log written by a newer version remains readable by the same MAJOR
line. If you downgrade across a MAJOR boundary, delete `agentrouter.db` if the
older version reports a schema error (no user data is lost — decisions are a log).

## Uninstall

```console
pip uninstall agentrouter-os
```

pip never removes local state. To purge it (decision log + config + seeded
registries), delete the home directory:

```console
rm -rf ~/.agentrouter        # or the path in $AGENTROUTER_HOME
```

Agent-host plugins installed via `agentrouter plugin install` live under your home
config (not `AGENTROUTER_HOME`); remove them with `agentrouter plugin uninstall <name>`
first. For a sandboxed or test install, set `AGENTROUTER_PLUGIN_ROOT` to redirect
where `plugin install` writes.

Plugin uninstall is conservative: a private ownership manifest records the installed digest and
filesystem identity, a `--force` replacement uses a metadata-preserving backup, and a transaction
journal recovers an interrupted replacement before later install/uninstall work. Later user edits,
unmanaged identical files, changed backups, and unrelated files are preserved. A declared
integration directory is removed non-recursively only when AgentRouter recorded creating that exact
directory and it is still empty; host configuration parents are never deleted.

Pre-v0.5 installations have no ownership manifest. If an existing file is byte-identical and you
know it was installed by AgentRouter, `agentrouter plugin install <name> --adopt-identical`
explicitly claims it so a later uninstall may remove it. Without that opt-in, uninstall preserves
the file. Link/reparse destinations, hard-linked replacement targets, unsafe portable names, and
ambiguous recovery state fail closed with a readable error.

## Supply chain

Each GitHub Release attaches a **CycloneDX SBOM** (`sbom.cdx.json`) and carries
**SLSA build provenance** (via GitHub artifact attestation). Verify a downloaded
artifact with:

```console
gh attestation verify <file> --repo krish17kp/AgentRouter-OS
```
