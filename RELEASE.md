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

## Later (when publishing to PyPI)

- Add a `publish` workflow triggered on release (trusted publishing, no token
  in repo)
- Verify `python -m build` + `twine check dist/*` locally first
- Test-install from TestPyPI before the real index
