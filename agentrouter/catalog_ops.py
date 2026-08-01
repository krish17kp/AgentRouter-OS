"""Provenance, freshness and rollback for refreshed provider catalogs (TASK-013).

`providers refresh` writes ``models.<provider>.generated.yaml`` next to the manual
``models.yaml`` (manual wins on collision). This module makes those generated
catalogs *trustworthy and reversible* without changing the refresh format or any
routing behavior:

* freshness — how old a generated catalog is, derived from the newest
  ``last_updated`` among its entries, judged against ``STALE_AFTER_DAYS``;
* status — a per-file summary (provider, count, newest date, age, fresh/stale);
* rollback — back up then remove a generated file, reverting to the manual
  registry (deleting the generated file is the documented revert path).

All functions are offline and read-only except ``rollback``, which only touches
the single generated file it is given (plus a ``.bak`` copy).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .registry import STALE_AFTER_DAYS

GENERATED_GLOB = "models.*.generated.yaml"


def _provider_of(path: Path) -> str:
    # models.<provider>.generated.yaml -> <provider>
    return path.name[len("models.") : -len(".generated.yaml")]


@dataclass(frozen=True)
class CatalogStatus:
    provider: str
    path: Path
    count: int
    newest: date | None  # newest last_updated among entries
    age_days: int | None  # today - newest; None when no dated entries
    stale: bool

    @property
    def summary(self) -> str:
        when = self.newest.isoformat() if self.newest else "unknown"
        age = "unknown" if self.age_days is None else f"{self.age_days}d"
        flag = "STALE" if self.stale else "fresh"
        return f"{self.provider:<12} {self.count:>4} models  newest {when} ({age})  {flag}"


def _newest_last_updated(models: list[dict]) -> date | None:
    dates: list[date] = []
    for m in models:
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
    """Freshness summary for one generated catalog file (offline, read-only)."""
    today = today or date.today()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    models = raw.get("models") or []
    newest = _newest_last_updated(models)
    age = (today - newest).days if newest else None
    stale = age is None or age > STALE_AFTER_DAYS
    return CatalogStatus(
        provider=_provider_of(path),
        path=path,
        count=len(models),
        newest=newest,
        age_days=age,
        stale=stale,
    )


def list_generated(reg_dir: Path, *, today: date | None = None) -> list[CatalogStatus]:
    """Status for every generated catalog in a registry directory, sorted by provider."""
    return [read_status(p, today=today) for p in sorted(reg_dir.glob(GENERATED_GLOB))]


def rollback(reg_dir: Path, provider: str) -> Path | None:
    """Revert a provider's generated catalog: back it up to ``.bak`` then remove it.

    Returns the backup path, or None if there was no generated file to roll back.
    The manual ``models.yaml`` is never touched, so routing reverts to it cleanly.
    """
    path = reg_dir / f"models.{provider}.generated.yaml"
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    path.unlink()
    return backup
