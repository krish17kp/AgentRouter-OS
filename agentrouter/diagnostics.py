"""Unified diagnostics behind `agentrouter doctor` (TASK-018C).

There were already three doctors — `providers doctor`, `hosts doctor` and
`plugin doctor` — each printing straight to stdout and exiting. This module does
not reimplement them: it calls the same underlying primitives they call
(`hosts.detect_host`, `catalog_ops.read_status`, `registry.load_providers`,
`store.connect`) and returns **structured** results, so one command can report
the whole system and a machine can consume it.

Two rules the checks obey without exception:

* **A check never raises.** A diagnostic tool that crashes on a broken system is
  useless precisely when it is needed, so every check catches its own failures
  and reports them as a result.
* **A check never prints a secret.** Presence is reported, never a value — the
  same rule host detection already follows.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OK = "ok"
WARN = "warn"
FAIL = "fail"
#: Ordered worst-first, so a report can be sorted by severity deterministically.
SEVERITY = (FAIL, WARN, OK)


@dataclass(frozen=True)
class Check:
    """One diagnostic result.

    ``id`` is stable and machine-readable so a runbook or a support request can
    name a specific check; ``remedy`` is the concrete next action, and is
    required whenever the status is not ``ok`` — a diagnosis without a fix just
    tells the user they have a problem.
    """

    id: str
    status: str
    summary: str
    remedy: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "summary": self.summary,
            "remedy": self.remedy,
        }


def _safe(check_id: str, fn) -> Check:
    """Run one check, converting any unexpected failure into a reportable result."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a doctor must not crash
        return Check(
            check_id,
            FAIL,
            f"check failed to run ({type(exc).__name__})",
            "this is a bug in the diagnostic itself; run with --json and report it",
        )


# --- individual checks --------------------------------------------------------


def check_version() -> Check:
    from . import __version__

    return Check("app.version", OK, f"agentrouter-os {__version__}")


def check_python() -> Check:
    major, minor = sys.version_info[:2]
    detail = f"Python {major}.{minor} on {platform.system()}"
    if (major, minor) < (3, 10):
        return Check("runtime.python", FAIL, detail, "AgentRouter needs Python 3.10 or newer")
    return Check("runtime.python", OK, detail)


def check_home(home: Path) -> Check:
    if not home.exists():
        return Check("data.home", FAIL, f"{home} does not exist", "run: agentrouter init")
    if not os.access(home, os.W_OK):
        return Check(
            "data.home",
            FAIL,
            f"{home} is not writable",
            "this machine has had its NTFS volume remount read-only; check the mount "
            "with: findmnt -T <path>",
        )
    return Check("data.home", OK, f"{home} exists and is writable")


def check_database(home: Path) -> Check:
    from . import store

    db = home / "agentrouter.db"
    if not db.exists():
        return Check("data.database", WARN, "no decision log yet", "run: agentrouter init")
    conn = store.connect(home)
    try:
        decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()

    if integrity != "ok":
        return Check(
            "data.database",
            FAIL,
            f"integrity check reported: {integrity}",
            "restore from a backup taken with `agentrouter doctor --bundle`, or "
            "move the database aside and re-run: agentrouter init",
        )
    if mode.lower() != "wal":
        # Not fatal, but it is the configuration that produced HTTP 500s under
        # concurrency before TASK-018B.
        return Check(
            "data.database",
            WARN,
            f"{decisions} decision(s), journal_mode={mode}",
            "WAL is expected; a non-WAL journal degrades under concurrent writes",
        )
    return Check("data.database", OK, f"{decisions} decision(s), WAL, integrity ok")


def check_registry(home: Path) -> Check:
    from .registry import RegistryError, load_models, load_providers

    reg = home / "registry"
    try:
        providers = load_providers(reg / "providers.yaml")
        models = load_models(reg / "models.yaml", providers)
    except RegistryError as exc:
        # The message can quote the offending file contents, so it is summarised
        # rather than echoed — the same reason the API returns a fixed message.
        return Check(
            "registry.load",
            FAIL,
            f"registry is missing or invalid ({type(exc).__name__})",
            "run: agentrouter init, or fix the YAML under ~/.agentrouter/registry",
        )
    return Check("registry.load", OK, f"{len(providers)} provider(s), {len(models)} model(s)")


def check_catalogs(home: Path) -> Check:
    from . import catalog_ops

    reg = home / "registry"
    if not reg.is_dir():
        return Check("catalogs.generated", WARN, "no registry directory", "run: agentrouter init")
    paths = sorted(reg.glob(catalog_ops.GENERATED_GLOB))
    if not paths:
        return Check(
            "catalogs.generated", OK, "none refreshed; manual models.yaml is authoritative"
        )

    stale, broken = [], []
    for path in paths:
        try:
            status = catalog_ops.read_status(path)
            if status.stale:
                stale.append(path.name)
        except Exception:  # noqa: BLE001 - a corrupt catalog is a finding, not a crash
            broken.append(path.name)

    if broken:
        return Check(
            "catalogs.generated",
            FAIL,
            f"{len(broken)} unreadable catalog(s): {', '.join(sorted(broken))}",
            "run: agentrouter providers doctor  (then providers rollback <provider>)",
        )
    if stale:
        return Check(
            "catalogs.generated",
            WARN,
            f"{len(stale)} stale catalog(s): {', '.join(sorted(stale))}",
            "run: agentrouter providers refresh <provider>",
        )
    return Check("catalogs.generated", OK, f"{len(paths)} catalog(s), all fresh")


def check_hosts() -> Check:
    from . import hosts

    ready, remedies = [], []
    for host in hosts.known_hosts():
        status = hosts.detect_host(host)
        # 'manual' is always available, so it must not mask a real host being ready.
        if status.availability == hosts.AVAILABLE and host != "manual":
            ready.append(host)
        elif status.remedy:
            remedies.append(f"{host}: {status.remedy}")

    if ready:
        return Check("hosts.ready", OK, f"ready: {', '.join(sorted(ready))}")
    return Check(
        "hosts.ready",
        WARN,
        "no execution host is ready; only manual execution is available",
        remedies[0] if remedies else "run: agentrouter hosts doctor",
    )


def check_server_extra() -> Check:
    try:
        import fastapi  # noqa: F401
    except ImportError:
        return Check(
            "server.extra",
            WARN,
            "the [server] extra is not installed; the REST API is unavailable",
            "install it with: pip install 'agentrouter-os[server]'",
        )
    return Check("server.extra", OK, "the [server] extra is installed")


def check_api_key_configured() -> Check:
    """Presence only. The value is never read beyond an emptiness test."""
    raw = os.environ.get("AGENTROUTER_API_KEY")
    if raw is None:
        return Check(
            "server.auth",
            WARN,
            "AGENTROUTER_API_KEY is unset; the local API is open",
            "set AGENTROUTER_API_KEY to require an X-API-Key header",
        )
    if not raw.strip():
        return Check(
            "server.auth",
            FAIL,
            "AGENTROUTER_API_KEY is set but blank",
            "unset it, or set it to a real value — a blank key rejects every request",
        )
    return Check("server.auth", OK, "AGENTROUTER_API_KEY is set")


def check_contract() -> Check:
    from . import contract

    return Check(
        "contract.version",
        OK,
        f"HTTP contract {contract.CONTRACT_VERSION} ({contract.CONTRACT_DIR})",
    )


def check_observability() -> Check:
    from . import observability

    enabled = observability._truthy(os.environ.get("AGENTROUTER_LOG"))
    otel = observability.otel_enabled()
    detail = f"structured logging {'on' if enabled else 'off'}, OTel {'on' if otel else 'off'}"
    return Check(
        "observability.logging",
        OK,
        detail,
        None if enabled else "set AGENTROUTER_LOG=1 to emit structured route records",
    )


def run_all(home: Path) -> list[Check]:
    """Every check, in a stable order. Never raises."""
    return [
        _safe("app.version", check_version),
        _safe("runtime.python", check_python),
        _safe("data.home", lambda: check_home(home)),
        _safe("data.database", lambda: check_database(home)),
        _safe("registry.load", lambda: check_registry(home)),
        _safe("catalogs.generated", lambda: check_catalogs(home)),
        _safe("hosts.ready", check_hosts),
        _safe("server.extra", check_server_extra),
        _safe("server.auth", check_api_key_configured),
        _safe("contract.version", check_contract),
        _safe("observability.logging", check_observability),
    ]


def worst(checks: list[Check]) -> str:
    """The most severe status present, for an exit code."""
    for severity in SEVERITY:
        if any(c.status == severity for c in checks):
            return severity
    return OK
