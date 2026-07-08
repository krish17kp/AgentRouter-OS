# Release Checklist

Not published to PyPI yet — releases are git tags + GitHub Releases for now.

## Before tagging

```console
# 1. Clean tree, up-to-date main
git status
git pull

# 2. Full local verification (same as CI)
ruff check .
ruff format --check .
pytest --cov=agentrouter

# 3. Secret scan — expect no matches in tracked files
git grep -nE "sk-or-v1|sk-proj|sk-ant|ghp_|AKIA[0-9A-Z]{16}" -- . ':!RELEASE.md'

# 4. Entrypoints
python -m agentrouter --help
agentrouter --help
```

## Cut the release

1. Bump `version` in `pyproject.toml` (SemVer).
2. Move `[Unreleased]` items in `CHANGELOG.md` under the new version + date.
3. Commit: `chore: release vX.Y.Z`
4. Tag and push:
   ```console
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push && git push --tags
   ```
5. Confirm CI is green on the tag, then create a GitHub Release from it,
   pasting the changelog section.

## Publishing to PyPI

The publish workflow exists: `.github/workflows/release.yml` builds sdist+wheel
and publishes via **trusted publishing** (OIDC — no token stored in the repo)
whenever a GitHub Release is published.

One-time setup (repo owner, on pypi.org):

1. Create/claim the `agentrouter-os` project name.
2. Project settings → Publishing → add a **trusted publisher**:
   owner `krish17kp`, repo `AgentRouter-OS`, workflow `release.yml`,
   environment `pypi`.
3. In the GitHub repo, create an environment named `pypi`
   (Settings → Environments).
4. Optional first dry-run: `python -m build && twine check dist/*` locally,
   and/or point the workflow at TestPyPI before the real index.

After that, step 5 above (publishing the GitHub Release) publishes to PyPI
automatically.
