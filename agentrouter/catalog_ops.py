"""Provenance, freshness and rollback for refreshed provider catalogs (TASK-013/015).

`providers refresh` writes ``models.<provider>.generated.yaml`` next to the manual
``models.yaml`` (manual wins on collision), with a top-level ``provenance`` block
(TASK-015) the registry loader ignores. This module makes those generated
catalogs *trustworthy and reversible* without changing the refresh format or any
routing behavior:

* freshness — how old a generated catalog is, derived from the newest
  ``last_updated`` among its entries, judged against ``STALE_AFTER_DAYS``;
* status — a per-file summary (provider, count, newest date, age, fresh/stale,
  provenance source/fetch time when present);
* rollback/restore — back up then remove a generated file (reverting to the
  manual registry), and reverse that if needed, without destroying prior
  backup history;
* deprecations — models present in one set of ids but not another (report-only;
  callers decide whether/when to act).

All functions are offline and read-only except ``rollback``/``restore``, which
only touch the single generated file (plus its ``.bak``) they are given.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .registry import STALE_AFTER_DAYS

GENERATED_GLOB = "models.*.generated.yaml"

# provider ids are ours (SUPPORTED_PROVIDERS) or user-placed filenames; constrain
# them before building a path so a hostile value can never escape reg_dir.
_PROVIDER_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


class CatalogError(Exception):
    """A generated catalog file could not be read/parsed — corrupt, not a bug."""


def _validate_provider(provider: str) -> None:
    if not _PROVIDER_ID_RE.fullmatch(provider):
        raise ValueError(f"invalid provider id: {provider!r}")


def _sanitize(value: str) -> str:
    """Strip control/escape characters before echoing untrusted file content to a terminal."""
    return "".join(c if c.isprintable() else "?" for c in value)[:120]


def _provider_of(path: Path) -> str:
    # models.<provider>.generated.yaml -> <provider>
    return path.name[len("models.") : -len(".generated.yaml")]


def _load_raw(path: Path) -> dict:
    """Read + parse a generated catalog's top-level mapping, or raise CatalogError.

    Never lets a corrupt file (non-UTF-8 bytes, invalid YAML, or a non-mapping
    document — e.g. a bare list) escape as an unhandled AttributeError/
    UnicodeDecodeError; every failure mode becomes one typed, catchable error.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise CatalogError(f"{path}: not valid UTF-8: {e}") from e
    except OSError as e:
        raise CatalogError(f"{path}: cannot read file: {e}") from e
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise CatalogError(f"{path}: invalid YAML: {e}") from e
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CatalogError(f"{path}: expected a mapping at the top level")
    return raw


@dataclass(frozen=True)
class CatalogStatus:
    provider: str
    path: Path
    count: int
    newest: date | None  # newest last_updated among entries
    age_days: int | None  # today - newest; None when no dated entries
    stale: bool
    source_url: str | None = None  # from the provenance block; None for pre-TASK-015 files
    fetched_at: str | None = None  # provenance fetched_at (UTC ISO-8601), if present
    tool_version: str | None = None  # agentrouter version that wrote this file, if present

    @property
    def summary(self) -> str:
        when = self.newest.isoformat() if self.newest else "unknown"
        age = "unknown" if self.age_days is None else f"{self.age_days}d"
        flag = "STALE" if self.stale else "fresh"
        line = f"{self.provider:<12} {self.count:>4} models  newest {when} ({age})  {flag}"
        if self.source_url:
            line += f"  source={self.source_url}"
        return line


def read_provenance(path: Path) -> dict | None:
    """Parse a generated catalog's top-level ``provenance`` block, if present.

    Returns None for pre-TASK-015 generated files (no provenance block) or any
    file that fails to parse — this is a best-effort read, never a hard error.
    """
    try:
        raw = _load_raw(path)
    except CatalogError:
        return None
    prov = raw.get("provenance")
    return prov if isinstance(prov, dict) else None


def deprecations(previous_ids: set[str], current_ids: set[str]) -> list[str]:
    """Ids present before but absent now — report-only, never auto-deleted."""
    return sorted(previous_ids - current_ids)


def _newest_last_updated(models: list) -> date | None:
    dates: list[date] = []
    for m in models:
        if not isinstance(m, dict):
            continue
        raw = m.get("last_updated")
        if isinstance(raw, date):
            dates.append(raw)
        elif isinstance(raw, str) and raw:
            try:
                dates.append(date.fromisoformat(raw))
            except ValueError:
                continue
    return max(dates) if dates else None


def read_status(path: Path, *, today: date | None = None) -> CatalogStatus:
    """Freshness summary for one generated catalog file (offline, read-only).

    Raises CatalogError for a corrupt/unreadable file — callers (``providers
    status``/``doctor``) turn that into a clean per-file message, never a crash.
    """
    today = today or date.today()
    raw = _load_raw(path)
    models = raw.get("models")
    models = models if isinstance(models, list) else []
    newest = _newest_last_updated(models)
    age = (today - newest).days if newest else None
    stale = age is None or age > STALE_AFTER_DAYS
    prov = raw.get("provenance") if isinstance(raw.get("provenance"), dict) else {}
    source_url = prov.get("source_url")
    return CatalogStatus(
        provider=_provider_of(path),
        path=path,
        count=len(models),
        newest=newest,
        age_days=age,
        stale=stale,
        source_url=_sanitize(source_url) if isinstance(source_url, str) else None,
        fetched_at=prov.get("fetched_at"),
        tool_version=prov.get("tool_version"),
    )


def list_generated(reg_dir: Path, *, today: date | None = None) -> list[CatalogStatus]:
    """Status for every generated catalog in a registry directory, sorted by provider.

    Raises CatalogError (naming the offending file) if any one catalog is
    corrupt — callers wanting a per-file breakdown despite one bad file should
    use ``providers doctor``, which iterates and isolates failures itself.
    """
    return [read_status(p, today=today) for p in sorted(reg_dir.glob(GENERATED_GLOB))]


def _create_exclusive(dst: Path) -> int:
    """Open dst for writing, refusing to follow or overwrite anything already there.

    ``O_EXCL`` fails atomically if the path exists for *any* reason — a regular
    file, or a symlink (even a dangling one an attacker pre-planted to redirect
    the write) — so a backup/temp write can never be tricked into following a
    symlink to an out-of-tree target.
    """
    return os.open(str(dst), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)


def _rotate_backup(backup: Path) -> None:
    """Move an existing backup aside under a unique name; never overwrites history.

    Uses a nanosecond clock plus a collision-probe loop so two rollbacks within
    the same wall-clock second still each keep their own backup.
    """
    n = time.time_ns()
    while True:
        rotated = backup.with_suffix(backup.suffix + f".{n}")
        if not rotated.exists() and not rotated.is_symlink():
            break
        n += 1
    shutil.move(str(backup), str(rotated))


def rollback(reg_dir: Path, provider: str) -> Path | None:
    """Revert a provider's generated catalog: back it up to ``.bak`` then remove it.

    Returns the backup path, or None if there was no generated file to roll back.
    The manual ``models.yaml`` is never touched, so routing reverts to it cleanly.
    An existing ``.bak`` from a prior rollback is rotated aside (uniquely named)
    rather than overwritten, so repeated rollbacks never destroy earlier backup
    history — even two within the same second.
    """
    _validate_provider(provider)
    path = reg_dir / f"models.{provider}.generated.yaml"
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists() or backup.is_symlink():
        _rotate_backup(backup)
    fd = _create_exclusive(backup)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(path.read_bytes())
    except BaseException:
        backup.unlink(missing_ok=True)
        raise
    path.unlink()
    return backup


def restore(reg_dir: Path, provider: str) -> Path | None:
    """Reverse the most recent ``rollback``: move ``.bak`` back over the generated file.

    Returns the restored path, or None if there is no ``.bak`` to restore from.
    Refuses to clobber a generated file that already exists (re-refreshed since
    the rollback) — remove or roll it back first.
    """
    _validate_provider(provider)
    backup = reg_dir / f"models.{provider}.generated.yaml.bak"
    if not backup.exists():
        return None
    path = reg_dir / f"models.{provider}.generated.yaml"
    if path.exists():
        raise FileExistsError(
            f"{path} already exists — remove or roll it back before restoring the backup"
        )
    shutil.move(str(backup), str(path))  # os.rename semantics: replaces, never follows
    return path
