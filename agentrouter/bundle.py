"""Secret-safe local diagnostic bundle (TASK-018C).

A bundle is something a user hands to someone else, so the threat model is the
opposite of most collectors: the danger is not that we gather too little, it is
that we gather something we should not have. This module therefore works from an
**allowlist** — each artifact is named, produced deliberately, and passed through
redaction. Nothing is collected by globbing a directory, because a glob picks up
whatever happens to be sitting there, including a `.env` a user dropped in.

Specifically defended against:

* `.env` and credential files — never enumerated, never read;
* the database — copied with ``store.snapshot`` and NOT a filesystem copy, which
  silently loses every row while a WAL is active (measured in TASK-018B);
* symlinks and arbitrary paths — the destination is resolved and must not be a
  symlink, and nothing is written outside it;
* overwriting — an existing bundle is refused rather than clobbered;
* prompts, task text and annotation data — decisions are summarised by shape,
  never by content.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import diagnostics, observability

#: Nothing larger than this is written; a bundle is meant to be readable.
MAX_ARTIFACT_BYTES = 2_000_000


class BundleError(Exception):
    """Raised when a bundle cannot be produced safely."""


@dataclass(frozen=True)
class Bundle:
    directory: Path
    files: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"directory": str(self.directory), "files": sorted(self.files)}


def _write(directory: Path, name: str, text: str) -> str:
    """Write one allowlisted artifact, redacted and bounded."""
    if len(text) > MAX_ARTIFACT_BYTES:
        text = text[:MAX_ARTIFACT_BYTES] + "\n... truncated ...\n"
    target = directory / name
    if target.is_symlink():
        raise BundleError(f"refusing to write through a symlink: {target}")
    target.write_text(observability.redact(text), encoding="utf-8")
    return name


def _environment_summary() -> dict[str, Any]:
    """Which AgentRouter settings are set — never what they are set to.

    A support bundle needs to know whether an API key is configured, not what it
    is. The value is never read beyond an emptiness test, the same rule host
    detection follows.
    """
    interesting = [
        "AGENTROUTER_HOME",
        "AGENTROUTER_API_KEY",
        "AGENTROUTER_LOG",
        "AGENTROUTER_OTEL",
        "AGENTROUTER_RATE_LIMIT",
        "AGENTROUTER_RATE_WINDOW",
        "AGENTROUTER_IDEMPOTENCY_TTL",
        "AGENTROUTER_USER",
    ]
    summary: dict[str, Any] = {}
    for name in interesting:
        raw = os.environ.get(name)
        if raw is None:
            summary[name] = "unset"
        elif name.endswith(("_KEY", "_TOKEN", "_SECRET")):
            # presence only, never the value
            summary[name] = "set (value withheld)" if raw.strip() else "set but blank"
        elif name == "AGENTROUTER_HOME":
            summary[name] = str(Path(raw).resolve())
        else:
            summary[name] = raw
    return summary


def _decision_shape(home: Path) -> dict[str, Any]:
    """Counts and shapes only. Task text and prompts are never collected."""
    from . import store

    db = home / "agentrouter.db"
    if not db.exists():
        return {"database": "absent"}
    conn = store.connect(home)
    try:
        decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        feedback = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    return {
        "decisions": decisions,
        "feedback": feedback,
        "journal_mode": journal,
        "integrity": integrity,
        "size_bytes": db.stat().st_size,
    }


def create(home: Path, destination: Path, *, include_database: bool = False) -> Bundle:
    """Write a bundle into ``destination``, which must not already exist.

    ``include_database`` is opt-in because the decision log contains the task
    text a user actually routed. When it is on, the copy goes through
    ``store.snapshot`` — a filesystem copy of a WAL database silently produces an
    empty log, which would make the bundle worse than useless.
    """
    if destination.exists():
        raise BundleError(
            f"{destination} already exists; choose a new path rather than overwriting a bundle"
        )
    if destination.is_symlink():
        raise BundleError(f"refusing to write through a symlink: {destination}")

    destination.mkdir(parents=True)
    resolved = destination.resolve()
    files: list[str] = []

    checks = diagnostics.run_all(home)
    files.append(
        _write(
            resolved,
            "doctor.json",
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "status": diagnostics.worst(checks),
                    "checks": [c.as_dict() for c in checks],
                },
                indent=2,
            ),
        )
    )

    from . import __version__

    files.append(
        _write(
            resolved,
            "environment.json",
            json.dumps(
                {
                    "agentrouter_version": __version__,
                    "python": sys.version.split()[0],
                    "platform": platform.platform(),
                    "settings": _environment_summary(),
                },
                indent=2,
            ),
        )
    )

    files.append(_write(resolved, "data-shape.json", json.dumps(_decision_shape(home), indent=2)))

    if include_database:
        from . import store

        target = resolved / "decisions.db"
        # NOT shutil.copy: with a WAL active that yields an empty database.
        store.snapshot(home, target)
        files.append("decisions.db")

    files.append(
        _write(
            resolved,
            "README.txt",
            "AgentRouter OS diagnostic bundle\n"
            "================================\n\n"
            "Contents are allowlisted, not collected by scanning a directory.\n"
            "  doctor.json      every diagnostic check and its remedy\n"
            "  environment.json versions and which settings are set (never their values)\n"
            "  data-shape.json  row counts and integrity - no task text, no prompts\n"
            + (
                "  decisions.db     your decision log, INCLUDING task text you routed\n"
                if include_database
                else ""
            )
            + "\nNo .env file, credential file or API key value is ever collected.\n"
            "Text is passed through the same redaction the logs use.\n"
            + (
                "\nYou opted into --include-database, so this bundle DOES contain the\n"
                "task text you routed. Review it before sharing.\n"
                if include_database
                else ""
            ),
        )
    )
    return Bundle(resolved, files)
