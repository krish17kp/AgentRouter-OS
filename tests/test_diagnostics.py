"""Unified `agentrouter doctor` (TASK-018C).

Two properties matter more than the individual checks:

* **a doctor must not crash on a broken system**, because that is exactly when
  someone runs it;
* **a doctor must never print a secret**, because people paste its output into
  support requests.
"""

from __future__ import annotations

import builtins
import json
import os
import stat

import pytest
from typer.testing import CliRunner

from agentrouter import diagnostics
from agentrouter.cli import app

runner = CliRunner()
SECRET = "sk-livekey0123456789abcdefghij"


def test_a_healthy_install_reports_no_failures_and_exits_zero(home):
    """Open local mode with no API key is the DOCUMENTED default, so a fresh
    healthy install must not exit non-zero — that would cry wolf on the happy
    path and make the command useless in a script."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    checks = diagnostics.run_all(home)
    assert [c for c in checks if c.status == diagnostics.FAIL] == []


def test_a_broken_registry_fails_with_a_remedy(home):
    (home / "registry" / "providers.yaml").unlink()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "registry.load" in result.output
    assert "agentrouter init" in result.output


@pytest.mark.parametrize(
    ("name", "break_it"),
    [
        ("no registry dir", lambda h: __import__("shutil").rmtree(h / "registry")),
        ("truncated database", lambda h: (h / "agentrouter.db").write_bytes(b"not a database")),
        (
            "registry is a file",
            lambda h: (
                __import__("shutil").rmtree(h / "registry"),
                (h / "registry").write_text("x"),
            ),
        ),
    ],
)
def test_the_doctor_never_crashes_on_a_broken_system(home, name, break_it):
    """A diagnostic that raises is useless precisely when it is needed."""
    break_it(home)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1), f"{name}: {result.output}"
    assert "Traceback" not in result.output, name
    # every check still reported something
    assert result.output.count("[") >= 8, name


def test_no_check_ever_raises_directly(home):
    """`run_all` is the contract: it returns results, it does not propagate."""
    import shutil

    shutil.rmtree(home / "registry")
    (home / "agentrouter.db").write_bytes(b"corrupt")
    checks = diagnostics.run_all(home)
    assert len(checks) >= 8
    assert all(isinstance(c, diagnostics.Check) for c in checks)


def test_database_diagnostic_is_read_only_and_actionable(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    database = home / "agentrouter.db"
    database.write_bytes(b"")

    check = diagnostics.check_database(home)

    assert check.status == diagnostics.FAIL
    assert check.summary == "decision log is unreadable (OperationalError)"
    assert "restore from a backup" in check.remedy
    assert database.read_bytes() == b""
    assert not (home / "agentrouter.db-wal").exists()


def test_every_non_ok_check_carries_a_remedy(home):
    """A diagnosis without a fix just tells the user they have a problem."""
    (home / "registry" / "providers.yaml").unlink()
    for check in diagnostics.run_all(home):
        if check.status != diagnostics.OK:
            assert check.remedy, f"{check.id} has no remedy"


def test_the_api_key_value_is_never_printed(home, monkeypatch):
    """Presence is reported; the value never is."""
    monkeypatch.setenv("AGENTROUTER_API_KEY", SECRET)
    result = runner.invoke(app, ["doctor"])
    assert SECRET not in result.output
    assert "AGENTROUTER_API_KEY is set" in result.output


def test_a_blank_api_key_is_a_failure_not_a_pass(home, monkeypatch):
    """A set-but-blank key rejects every request — the same class of bug that
    made host detection report a blank credential as available (TASK-016)."""
    monkeypatch.setenv("AGENTROUTER_API_KEY", "   ")
    check = diagnostics.check_api_key_configured()
    assert check.status == diagnostics.FAIL
    assert check.remedy


def test_registry_failure_does_not_echo_the_file_contents(home):
    """A malformed registry is exactly when someone has pasted a credential."""
    (home / "registry" / "providers.yaml").write_text(
        f'providers:\n  - id: x\n    token: "{SECRET}\n', encoding="utf-8"
    )
    result = runner.invoke(app, ["doctor"])
    assert SECRET not in result.output
    assert str(home) not in result.output or "data.home" in result.output


def test_json_output_is_machine_readable(home):
    result = runner.invoke(app, ["doctor", "--json"])
    payload = json.loads(result.output)
    assert payload["status"] in (diagnostics.OK, diagnostics.WARN, diagnostics.FAIL)
    ids = [c["id"] for c in payload["checks"]]
    assert "data.database" in ids and "registry.load" in ids
    assert len(set(ids)) == len(ids), "check ids must be unique and stable"


def test_check_ids_are_stable_identifiers(home):
    """Runbooks and support requests name these, so they are an interface."""
    ids = {c.id for c in diagnostics.run_all(home)}
    assert {
        "app.version",
        "runtime.python",
        "data.home",
        "data.database",
        "registry.load",
        "catalogs.generated",
        "hosts.ready",
        "server.extra",
        "server.auth",
        "contract.version",
        "observability.logging",
    } <= ids


def test_harness_check_is_always_present_and_never_a_secret_leak(home, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    result = runner.invoke(app, ["doctor"])
    assert "environment.harness" in result.output
    assert SECRET not in result.output


def test_verify_live_reports_unsupported_for_every_real_provider(home, monkeypatch):
    """No adapter is registered in production, so every authenticated provider
    honestly reports 'unsupported' — never a guessed quota number."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    result = runner.invoke(app, ["doctor", "--verify-live"])
    assert result.exit_code == 0, result.output
    assert "usage.openai-api" in result.output
    assert "unsupported" in result.output


def test_verify_live_is_opt_in_and_absent_by_default(home, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    result = runner.invoke(app, ["doctor"])
    assert "usage.openai-api" not in result.output


def test_verify_live_skips_unauthenticated_hosts_without_checking(home, monkeypatch):
    for env in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    result = runner.invoke(app, ["doctor", "--verify-live", "--json"])
    payload = json.loads(result.output)
    usage_checks = [c for c in payload["checks"] if c["id"].startswith("usage.")]
    assert usage_checks
    assert all(c["summary"] == "not authenticated; usage not checked" for c in usage_checks)


def test_verify_live_and_route_verify_live_query_the_same_provider_key(home, monkeypatch):
    """Regression: doctor's usage checks used to look up by API host id
    ('openai-api') while route's looked up by provider id ('openai') — a
    registered adapter would only ever fire on one of the two paths."""
    from agentrouter import hosts, usage

    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    seen = []

    def fake(t):
        seen.append(True)
        return usage.UsageStatus("openai", usage.AVAILABLE, "ok")

    usage.register_live_check("openai", fake)
    try:
        result = runner.invoke(app, ["doctor", "--verify-live", "--json"])
        payload = json.loads(result.output)
        check = next(c for c in payload["checks"] if c["id"] == "usage.openai-api")
        assert check["summary"] == "available: ok"
        assert seen == [True]
        assert hosts.provider_for_api_host("openai-api") == "openai"
    finally:
        usage.unregister_live_check("openai")


def test_exhausted_usage_check_is_a_warning_with_a_remedy(home, monkeypatch):
    from agentrouter import diagnostics

    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    monkeypatch.setattr(
        diagnostics,
        "check_usage_for",
        lambda host: diagnostics.Check(
            f"usage.{host}", diagnostics.WARN, "exhausted: none left", "wait or switch providers"
        ),
    )
    result = runner.invoke(app, ["doctor", "--verify-live"])
    assert result.exit_code == 0, result.output  # WARN never fails doctor
    assert "exhausted" in result.output
    assert "wait or switch providers" in result.output


def test_verify_live_isolates_one_broken_provider_check(home, monkeypatch):
    """A provider check that raises must not crash doctor or hide the others."""
    from agentrouter import diagnostics

    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")

    def boom(host):
        raise RuntimeError("simulated provider check crash")

    monkeypatch.setattr(diagnostics, "check_usage_for", boom)
    result = runner.invoke(app, ["doctor", "--verify-live"])
    assert result.exit_code in (0, 1), result.output
    assert "Traceback" not in result.output
    assert "usage.openai-api" in result.output


def test_an_unwritable_home_is_reported_with_the_mount_hint(home):
    """This project has actually had its NTFS volume remount read-only."""
    mode = home.stat().st_mode
    os.chmod(home, stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(home, os.W_OK):
            pytest.skip("cannot drop write permission as this user")
        check = diagnostics.check_home(home)
        assert check.status == diagnostics.FAIL
        assert "findmnt" in (check.remedy or "")
    finally:
        os.chmod(home, mode)


def test_home_and_database_missing_checks_are_actionable(tmp_path):
    assert diagnostics.check_home(tmp_path / "missing").status == diagnostics.FAIL
    check = diagnostics.check_database(tmp_path)
    assert check.status == diagnostics.WARN
    assert "no decision log" in check.summary


def test_database_non_wal_and_bad_integrity_are_reported(tmp_path, monkeypatch):
    db_path = tmp_path / "agentrouter.db"
    db_path.touch()

    class FakeConnection:
        def __init__(self, rows):
            self.rows = iter(rows)
            self.closed = False

        def execute(self, _query):
            return self

        def fetchone(self):
            return next(self.rows)

        def close(self):
            self.closed = True

    conn = FakeConnection([(2,), ("delete",), ("ok",)])
    monkeypatch.setattr(diagnostics.sqlite3, "connect", lambda *_args, **_kwargs: conn)
    assert diagnostics.check_database(tmp_path).status == diagnostics.WARN
    assert conn.closed

    conn = FakeConnection([(0,), ("wal",), ("malformed page",)])
    monkeypatch.setattr(diagnostics.sqlite3, "connect", lambda *_args, **_kwargs: conn)
    check = diagnostics.check_database(tmp_path)
    assert check.status == diagnostics.FAIL
    assert "malformed page" in check.summary


def test_catalog_diagnostics_report_fresh_stale_and_corrupt(home, monkeypatch):
    from agentrouter import catalog_ops

    reg = home / "registry"
    check = diagnostics.check_catalogs(home)
    assert check.status == diagnostics.OK
    assert "none refreshed" in check.summary

    fresh = reg / "models.fresh.generated.yaml"
    fresh.write_text("models:\n  - last_updated: '2026-11-11'\n", encoding="utf-8")
    assert diagnostics.check_catalogs(home).status == diagnostics.OK

    monkeypatch.setattr(
        catalog_ops, "read_status", lambda _path: type("Status", (), {"stale": True})()
    )
    check = diagnostics.check_catalogs(home)
    assert check.status == diagnostics.WARN
    assert "stale catalog" in check.summary

    def broken(_path):
        raise catalog_ops.CatalogError("bad yaml")

    monkeypatch.setattr(catalog_ops, "read_status", broken)
    check = diagnostics.check_catalogs(home)
    assert check.status == diagnostics.FAIL
    assert "unreadable catalog" in check.summary


def test_host_check_reports_manual_fallback_and_ready_host(monkeypatch):
    from agentrouter import hosts

    monkeypatch.setattr(hosts, "known_hosts", lambda: ["manual", "openai-api"])
    monkeypatch.setattr(
        hosts,
        "detect_host",
        lambda host: type(
            "Status",
            (),
            {"availability": hosts.UNAVAILABLE, "remedy": "configure credentials"},
        )(),
    )
    check = diagnostics.check_hosts()
    assert check.status == diagnostics.WARN
    assert "configure credentials" in check.remedy

    monkeypatch.setattr(
        hosts,
        "detect_host",
        lambda host: type(
            "Status",
            (),
            {
                "availability": hosts.AVAILABLE if host == "openai-api" else hosts.UNAVAILABLE,
                "remedy": None,
            },
        )(),
    )
    assert diagnostics.check_hosts().summary == "ready: openai-api"


def test_plugin_diagnostic_states_and_empty_severity(monkeypatch):
    from agentrouter import plugins

    monkeypatch.setattr(plugins, "diagnose_all", lambda: [])
    assert diagnostics.check_plugins().status == diagnostics.OK

    monkeypatch.setattr(
        plugins,
        "diagnose_all",
        lambda: [{"status": plugins.DIAG_BLOCKED, "remedy": None}],
    )
    blocked = diagnostics.check_plugins()
    assert blocked.status == diagnostics.FAIL
    assert blocked.remedy == "run: agentrouter plugin doctor"

    monkeypatch.setattr(
        plugins,
        "diagnose_all",
        lambda: [{"status": plugins.DIAG_ATTENTION, "remedy": "inspect manifest"}],
    )
    attention = diagnostics.check_plugins()
    assert attention.status == diagnostics.WARN
    assert attention.remedy == "inspect manifest"
    assert diagnostics.worst([]) == diagnostics.OK


def test_old_python_and_missing_server_extra_are_reported(monkeypatch):
    monkeypatch.setattr(diagnostics.sys, "version_info", (3, 9, 9))
    assert diagnostics.check_python().status == diagnostics.FAIL

    original_import = builtins.__import__

    def without_fastapi(name, *args, **kwargs):
        if name == "fastapi":
            raise ImportError("simulated optional dependency absence")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_fastapi)
    check = diagnostics.check_server_extra()
    assert check.status == diagnostics.WARN
    assert "not installed" in check.summary
