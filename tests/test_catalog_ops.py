"""Tests for catalog provenance/freshness/rollback (TASK-013).

Offline and deterministic: freshness is judged from the newest ``last_updated``
among a generated catalog's entries against ``STALE_AFTER_DAYS``; rollback backs
up then removes only the generated file, leaving the manual registry intact.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import yaml
from typer.testing import CliRunner

from agentrouter import catalog_ops
from agentrouter.cli import app
from agentrouter.registry import STALE_AFTER_DAYS

runner = CliRunner()


def _write_generated(reg_dir, provider, last_updated_dates, provenance=None):
    reg_dir.mkdir(parents=True, exist_ok=True)
    models = [
        {"provider": provider, "model_id": f"m{i}", "last_updated": d.isoformat()}
        for i, d in enumerate(last_updated_dates)
    ]
    doc = {"models": models}
    if provenance is not None:
        doc = {"provenance": provenance, **doc}
    path = reg_dir / f"models.{provider}.generated.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


def _write_valid_generated(reg_dir, provider, model_id="m0"):
    """A generated catalog whose entry fully validates against ModelEntry (for doctor tests)."""
    reg_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "provenance": {
            "provider": provider,
            "source_url": "https://example.invalid/models",
            "fetched_at": "2026-08-08T00:00:00+00:00",
            "count": 1,
            "tool_version": "0.5.0",
            "cli_args": {},
        },
        "models": [
            {
                "provider": provider,
                "model_id": model_id,
                "context_window": 8000,
                "max_output_tokens": 2000,
                "pricing_tier": "low",
                "latency_tier": "medium",
                "ability": {"coding": 6, "reasoning": 6, "writing": 6},
                "tool_support": [],
                "vision_support": False,
                "deprecation_status": "active",
                "last_updated": date.today().isoformat(),
            }
        ],
    }
    path = reg_dir / f"models.{provider}.generated.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
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


# --- provenance (TASK-015) ---------------------------------------------------


def test_read_provenance_present():
    import tempfile
    from pathlib import Path

    prov = {"provider": "openrouter", "source_url": "https://x", "fetched_at": "t", "count": 1}
    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = _write_generated(reg, "openrouter", [date(2026, 8, 1)], provenance=prov)
        assert catalog_ops.read_provenance(path) == prov


def test_read_provenance_absent_for_legacy_file():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = _write_generated(reg, "openrouter", [date(2026, 8, 1)])  # no provenance block
        assert catalog_ops.read_provenance(path) is None


def test_read_status_surfaces_provenance_fields():
    import tempfile
    from pathlib import Path

    prov = {
        "provider": "openrouter",
        "source_url": "https://openrouter.ai/api/v1/models",
        "fetched_at": "2026-08-08T00:00:00+00:00",
        "tool_version": "0.5.0",
    }
    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = _write_generated(reg, "openrouter", [date(2026, 8, 1)], provenance=prov)
        st = catalog_ops.read_status(path, today=date(2026, 8, 1))
        assert st.source_url == prov["source_url"]
        assert st.fetched_at == prov["fetched_at"]
        assert st.tool_version == prov["tool_version"]
        assert "source=https://openrouter.ai" in st.summary


def test_read_status_legacy_file_has_none_provenance():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = _write_generated(reg, "openrouter", [date(2026, 8, 1)])
        st = catalog_ops.read_status(path, today=date(2026, 8, 1))
        assert st.source_url is None and st.fetched_at is None and st.tool_version is None


# --- deprecations --------------------------------------------------------------


def test_deprecations_is_a_reported_set_difference():
    got = catalog_ops.deprecations({"a", "b", "c"}, {"b", "c"})
    assert got == ["a"]


def test_deprecations_empty_when_nothing_dropped():
    assert catalog_ops.deprecations({"a", "b"}, {"a", "b", "c"}) == []


# --- rollback / restore ------------------------------------------------------


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


def test_rollback_rotates_prior_backup_instead_of_overwriting():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        _write_generated(reg, "openrouter", [date(2026, 1, 1)])
        first_backup = catalog_ops.rollback(reg, "openrouter")
        first_content = first_backup.read_text(encoding="utf-8")

        # re-refresh, then roll back again — the first backup must survive, rotated aside
        _write_generated(reg, "openrouter", [date(2026, 2, 1)])
        second_backup = catalog_ops.rollback(reg, "openrouter")

        rotated = [p for p in reg.iterdir() if p.name.startswith(first_backup.name + ".")]
        assert rotated, "prior backup should have been rotated aside, not lost"
        assert rotated[0].read_text(encoding="utf-8") == first_content
        assert second_backup.exists()
        assert "2026-02-01" in second_backup.read_text(encoding="utf-8")


def test_restore_reverses_rollback():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = _write_generated(reg, "openrouter", [date(2026, 8, 1)])
        original = path.read_text(encoding="utf-8")
        catalog_ops.rollback(reg, "openrouter")
        assert not path.exists()

        restored = catalog_ops.restore(reg, "openrouter")
        assert restored == path
        assert path.exists()
        assert path.read_text(encoding="utf-8") == original
        assert not (reg / "models.openrouter.generated.yaml.bak").exists()


def test_restore_missing_backup_returns_none():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        assert catalog_ops.restore(Path(d), "openrouter") is None


def test_restore_refuses_to_clobber_existing_generated_file():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        _write_generated(reg, "openrouter", [date(2026, 1, 1)])
        catalog_ops.rollback(reg, "openrouter")
        _write_generated(reg, "openrouter", [date(2026, 2, 1)])  # re-refreshed since rollback

        import pytest

        with pytest.raises(FileExistsError):
            catalog_ops.restore(reg, "openrouter")


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
    assert "providers restore openrouter" in r.output
    # second rollback: nothing to revert -> usage error
    r2 = runner.invoke(app, ["providers", "rollback", "openrouter"])
    assert r2.exit_code == 2 and "No generated catalog" in r2.output


def test_cli_providers_restore_round_trip(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    path = _write_generated(reg, "openrouter", [date.today()])
    original = path.read_text(encoding="utf-8")
    assert runner.invoke(app, ["providers", "rollback", "openrouter"]).exit_code == 0

    r = runner.invoke(app, ["providers", "restore", "openrouter"])
    assert r.exit_code == 0, r.output
    assert path.exists() and path.read_text(encoding="utf-8") == original


def test_cli_providers_restore_missing_is_usage_error(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    r = runner.invoke(app, ["providers", "restore", "openrouter"])
    assert r.exit_code == 2 and "No rollback backup" in r.output


def test_cli_providers_doctor_ok_on_valid_catalog(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    _write_valid_generated(reg, "openrouter")
    r = runner.invoke(app, ["providers", "doctor"])
    assert r.exit_code == 0, r.output
    assert "OK" in r.output and "openrouter" in r.output


def test_cli_providers_doctor_no_generated_catalogs(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    r = runner.invoke(app, ["providers", "doctor"])
    assert r.exit_code == 0
    assert "No refreshed catalogs to check" in r.output


def test_cli_providers_doctor_flags_corrupt_yaml(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    (reg / "models.openai.generated.yaml").write_text(
        "models: [this is: not: valid: yaml", encoding="utf-8"
    )
    r = runner.invoke(app, ["providers", "doctor"])
    assert r.exit_code == 3  # EXIT_REGISTRY
    assert "FAIL" in r.output and "openai" in r.output
    assert "corrupt or invalid" in r.output


def test_cli_providers_doctor_flags_schema_invalid_entry(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    _write_generated(reg, "openrouter", [date.today()])  # missing required ModelEntry fields
    r = runner.invoke(app, ["providers", "doctor"])
    assert r.exit_code == 3
    assert "FAIL" in r.output and "openrouter" in r.output


def test_cli_providers_doctor_one_bad_one_good(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    _write_valid_generated(reg, "openai")
    (reg / "models.openrouter.generated.yaml").write_text(
        "models: [this is: not: valid: yaml", encoding="utf-8"
    )
    r = runner.invoke(app, ["providers", "doctor"])
    assert r.exit_code == 3
    assert "[OK" in r.output and "openai" in r.output
    assert "[FAIL" in r.output and "openrouter" in r.output


# --- corruption edge cases (security review follow-up) -----------------------


def test_read_status_raises_catalogerror_on_non_dict_root():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = reg / "models.openrouter.generated.yaml"
        reg.mkdir(exist_ok=True)
        path.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(catalog_ops.CatalogError, match="mapping"):
            catalog_ops.read_status(path)


def test_read_status_raises_catalogerror_on_non_utf8():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = reg / "models.openrouter.generated.yaml"
        reg.mkdir(exist_ok=True)
        path.write_bytes(b"\xff\xfe\x00bad")
        with pytest.raises(catalog_ops.CatalogError, match="UTF-8"):
            catalog_ops.read_status(path)


def test_read_provenance_never_raises_on_non_dict_root():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        path = reg / "models.openrouter.generated.yaml"
        reg.mkdir(exist_ok=True)
        path.write_text("- a\n- b\n", encoding="utf-8")
        assert catalog_ops.read_provenance(path) is None


def test_cli_providers_doctor_reports_non_dict_root_cleanly(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    (reg / "models.openrouter.generated.yaml").write_text("- a\n- b\n", encoding="utf-8")
    r = runner.invoke(app, ["providers", "doctor"])
    assert r.exit_code == 3
    assert "[FAIL" in r.output and "mapping" in r.output


def test_cli_providers_status_reports_corrupt_file_without_crashing(tmp_path, monkeypatch):
    reg = _home(tmp_path, monkeypatch)
    (reg / "models.openrouter.generated.yaml").write_bytes(b"\xff\xfe\x00bad")
    r = runner.invoke(app, ["providers", "status"])
    assert r.exit_code == 3
    assert "providers doctor" in r.output


# --- provider-id validation (defense in depth) --------------------------------


def test_rollback_rejects_invalid_provider_id():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ValueError, match="invalid provider"):
            catalog_ops.rollback(Path(d), "../../escape")


def test_restore_rejects_invalid_provider_id():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ValueError, match="invalid provider"):
            catalog_ops.restore(Path(d), "a/../../b")


def test_cli_providers_rollback_rejects_invalid_provider(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    r = runner.invoke(app, ["providers", "rollback", "../escape"])
    assert r.exit_code == 2 and "invalid provider" in r.output


# --- backup rotation never collides/destroys history --------------------------


def test_rotate_backup_advances_past_same_nanosecond_collision(monkeypatch):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        backup = reg / "models.openrouter.generated.yaml.bak"
        backup.write_text("first")

        # force every candidate rotated name to collide until the loop advances twice
        calls = {"n": 0}
        real_time_ns = catalog_ops.time.time_ns

        def frozen_time_ns():
            calls["n"] += 1
            return 12345  # constant — forces the collision-probe loop to fire

        monkeypatch.setattr(catalog_ops.time, "time_ns", frozen_time_ns)
        pre_existing = backup.with_suffix(backup.suffix + ".12345")
        pre_existing.write_text("pretend an earlier rotation already used this name")

        catalog_ops._rotate_backup(backup)
        monkeypatch.setattr(catalog_ops.time, "time_ns", real_time_ns)

        assert pre_existing.read_text() == "pretend an earlier rotation already used this name"
        prefix = backup.name + "."
        rotated = [p for p in reg.iterdir() if p.name.startswith(prefix) and p != pre_existing]
        assert len(rotated) == 1  # advanced past the collision to a new, distinct name
        assert rotated[0].read_text() == "first"


# --- symlink defense (security review) ----------------------------------------


@pytest.mark.skipif(
    __import__("sys").platform == "win32", reason="symlink creation needs elevated perms on Windows"
)
def test_rollback_does_not_follow_planted_symlink_backup():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        reg = Path(d)
        outside = Path(d).parent / "catalog_ops_symlink_victim.txt"
        outside.write_text("PRISTINE")
        try:
            _write_generated(reg, "openrouter", [date(2026, 1, 1)])
            (reg / "models.openrouter.generated.yaml.bak").symlink_to(outside)

            catalog_ops.rollback(reg, "openrouter")  # must not raise, must not follow the symlink

            assert outside.read_text() == "PRISTINE"
        finally:
            outside.unlink(missing_ok=True)
