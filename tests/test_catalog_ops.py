"""Tests for catalog provenance/freshness/rollback (TASK-013).

Offline and deterministic: freshness is judged from the newest ``last_updated``
among a generated catalog's entries against ``STALE_AFTER_DAYS``; rollback backs
up then removes only the generated file, leaving the manual registry intact.
"""

from __future__ import annotations

from datetime import date, timedelta

import yaml
from typer.testing import CliRunner

from agentrouter import catalog_ops
from agentrouter.cli import app
from agentrouter.registry import STALE_AFTER_DAYS

runner = CliRunner()


def _write_generated(reg_dir, provider, last_updated_dates):
    reg_dir.mkdir(parents=True, exist_ok=True)
    models = [
        {"provider": provider, "model_id": f"m{i}", "last_updated": d.isoformat()}
        for i, d in enumerate(last_updated_dates)
    ]
    path = reg_dir / f"models.{provider}.generated.yaml"
    path.write_text(yaml.safe_dump({"models": models}), encoding="utf-8")
    return path


# --- read_status ------------------------------------------------------------


def test_read_status_fresh_uses_newest_date():
    today = date(2026, 8, 1)
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        _write_generated(reg, "openrouter", [today - timedelta(days=40), today - timedelta(days=3)])
        st = catalog_ops.read_status(reg / "models.openrouter.generated.yaml", today=today)
        assert st.provider == "openrouter"
        assert st.count == 2
        assert st.newest == today - timedelta(days=3)  # newest wins
        assert st.age_days == 3
        assert st.stale is False


def test_read_status_stale_when_beyond_threshold():
    today = date(2026, 8, 1)
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        old = today - timedelta(days=STALE_AFTER_DAYS + 5)
        _write_generated(reg, "openai", [old])
        st = catalog_ops.read_status(reg / "models.openai.generated.yaml", today=today)
        assert st.stale is True and st.age_days == STALE_AFTER_DAYS + 5


def test_read_status_no_dates_is_stale():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = reg / "models.x.generated.yaml"
        reg.mkdir(exist_ok=True)
        path.write_text(yaml.safe_dump({"models": [{"provider": "x", "model_id": "m"}]}), "utf-8")
        st = catalog_ops.read_status(path)
        assert st.newest is None and st.age_days is None and st.stale is True


def test_list_generated_sorted_by_file():
    today = date(2026, 8, 1)
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        _write_generated(reg, "openrouter", [today])
        _write_generated(reg, "openai", [today])
        got = [s.provider for s in catalog_ops.list_generated(reg, today=today)]
        assert got == ["openai", "openrouter"]  # sorted by filename


# --- rollback ---------------------------------------------------------------


def test_rollback_backs_up_and_removes():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = _write_generated(reg, "openrouter", [date(2026, 8, 1)])
        backup = catalog_ops.rollback(reg, "openrouter")
        assert backup is not None and backup.exists()
        assert not path.exists()  # generated file removed
        # backup preserves content
        assert "models" in yaml.safe_load(backup.read_text(encoding="utf-8"))


def test_rollback_missing_returns_none():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        assert catalog_ops.rollback(Path(d), "nope") is None


# --- CLI --------------------------------------------------------------------


def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0
    return tmp_path / "registry"


def test_cli_providers_status_reports_and_flags_stale(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    _write_generated(reg, "openrouter", [date.today() - timedelta(days=STALE_AFTER_DAYS + 1)])
    r = runner.invoke(app, ["providers", "status"])
    assert r.exit_code == 0, r.output
    assert "openrouter" in r.output and "STALE" in r.output


def test_cli_providers_status_none_when_no_generated(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    r = runner.invoke(app, ["providers", "status"])
    assert r.exit_code == 0 and "No refreshed catalogs" in r.output


def test_cli_providers_rollback_then_missing(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    _write_generated(reg, "openrouter", [date.today()])
    r = runner.invoke(app, ["providers", "rollback", "openrouter"])
    assert r.exit_code == 0, r.output
    assert not (reg / "models.openrouter.generated.yaml").exists()
    assert (reg / "models.openrouter.generated.yaml.bak").exists()
    # second rollback: nothing to revert -> usage error
    r2 = runner.invoke(app, ["providers", "rollback", "openrouter"])
    assert r2.exit_code == 2 and "No generated catalog" in r2.output
