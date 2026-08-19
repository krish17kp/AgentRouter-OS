"""Soak profile: does the server degrade when it is merely used for a while?

Deliberately **not** part of ordinary CI. A soak is a wall-clock experiment, and
gating every pull request on one buys flakiness rather than confidence. It is run
locally, or on demand, and it reports rather than asserts thresholds — except for
the one thing that is unambiguously a defect at any duration: an unexpected 5xx.

Run:

    python -m agentrouter.reliability.soak --seconds 120 --workers 8
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .harness import LoadSpec, run_load, serve_app


@dataclass
class Sample:
    at_seconds: float
    rss_kb: int
    open_fds: int
    db_bytes: int
    wal_bytes: int
    ok: int
    server_errors: int


@dataclass
class SoakResult:
    samples: list[Sample] = field(default_factory=list)
    total_ok: int = 0
    total_server_errors: int = 0
    transport_errors: dict[str, int] = field(default_factory=dict)

    def growth(self, attribute: str) -> tuple[int, int, float]:
        """(first, last, ratio) for a monotonic-ish resource measure."""
        if not self.samples:
            return 0, 0, 0.0
        first = getattr(self.samples[0], attribute)
        last = getattr(self.samples[-1], attribute)
        return first, last, (last / first) if first else 0.0

    def as_dict(self) -> dict[str, Any]:
        rss = self.growth("rss_kb")
        fds = self.growth("open_fds")
        db = self.growth("db_bytes")
        return {
            "cycles": len(self.samples),
            "total_ok": self.total_ok,
            "total_server_errors": self.total_server_errors,
            "transport_errors": self.transport_errors,
            # Reported for a human to read, not asserted. A soak on a shared
            # machine cannot support a threshold that means anything.
            "resource_trend_indicative_only": {
                "rss_kb": {"first": rss[0], "last": rss[1], "ratio": round(rss[2], 2)},
                "open_fds": {"first": fds[0], "last": fds[1], "ratio": round(fds[2], 2)},
                "db_bytes": {"first": db[0], "last": db[1], "ratio": round(db[2], 2)},
            },
            "samples": [vars(s) for s in self.samples],
        }


def _open_fds() -> int:
    try:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    except OSError:  # pragma: no cover - non-Linux
        return -1


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def soak(home: Path, *, seconds: float, workers: int, batch: int) -> SoakResult:
    """Drive steady load for ``seconds``, sampling resources between batches."""
    result = SoakResult()
    started = time.perf_counter()
    with serve_app(home) as app:
        while time.perf_counter() - started < seconds:
            outcome = run_load(app.url, LoadSpec(total=batch, workers=workers))
            result.total_ok += outcome.ok
            result.total_server_errors += outcome.server_errors
            for name, count in outcome.transport_errors.items():
                result.transport_errors[name] = result.transport_errors.get(name, 0) + count
            result.samples.append(
                Sample(
                    at_seconds=round(time.perf_counter() - started, 1),
                    rss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    open_fds=_open_fds(),
                    db_bytes=_size(home / "agentrouter.db"),
                    wal_bytes=_size(home / "agentrouter.db-wal"),
                    ok=outcome.ok,
                    server_errors=outcome.server_errors,
                )
            )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--batch", type=int, default=50)
    parser.add_argument("--home", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    home = args.home or Path(tempfile.mkdtemp(prefix="agentrouter-soak-"))
    os.environ["AGENTROUTER_HOME"] = str(home)
    os.environ.pop("AGENTROUTER_API_KEY", None)

    from typer.testing import CliRunner

    from agentrouter.cli import app as cli_app

    if CliRunner().invoke(cli_app, ["init"]).exit_code != 0:
        print("could not initialise a soak home", file=sys.stderr)
        return 1

    result = soak(home, seconds=args.seconds, workers=args.workers, batch=args.batch)
    payload = result.as_dict()
    text = json.dumps(payload, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)

    # The one unambiguous defect at any duration.
    if result.total_server_errors or result.transport_errors:
        print(
            f"SOAK FAILED: {result.total_server_errors} server error(s), "
            f"{sum(result.transport_errors.values())} transport error(s)",
            file=sys.stderr,
        )
        return 1
    print(
        f"SOAK OK: {result.total_ok} requests over {len(result.samples)} cycles, "
        "no server or transport errors",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
