"""Rust providers-status probe matches the Python CLI's offline report."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from agentrouter.cli import app

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
runner = CliRunner()


def _rust_status(home, *, timeout=120):
    return subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "providers_status_cli", "--", str(home)],
        cwd="rust/agentrouter-cli",
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _python_status(home, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(home))
    return runner.invoke(app, ["providers", "status"])


def _write_catalog(home, provider, updated, source="https://example.test/catalog"):
    path = home / "registry" / f"models.{provider}.generated.yaml"
    updated_text = updated.isoformat() if isinstance(updated, date) else updated
    path.write_text(
        "provenance:\n"
        f"  source_url: {source}\n"
        "models:\n"
        f"  - model_id: {provider}-model\n"
        f'    last_updated: "{updated_text}"\n',
        encoding="utf-8",
    )
    return path


def test_empty_status_matches_python(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout


@pytest.mark.parametrize("age_days", [-3, 0, 90, 91, 365])
def test_freshness_status_matches_python(tmp_path, monkeypatch, age_days):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    _write_catalog(home, "beta", date.today() - timedelta(days=age_days))
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout


def test_multiple_statuses_are_sorted_like_python(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    _write_catalog(home, "zeta", date.today())
    _write_catalog(home, "alpha", date.today() - timedelta(days=91))
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout


def test_missing_registry_fails_without_stdout(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 3
    assert rust.stdout == ""
    assert rust.stderr == python.stderr


def test_corrupt_catalog_fails_without_partial_status(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    _write_catalog(home, "alpha", date.today())
    (home / "registry" / "models.beta.generated.yaml").write_text("[broken\n", encoding="utf-8")
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 3
    assert rust.stdout == ""
    assert "Next: agentrouter providers doctor" in rust.stderr


@pytest.mark.parametrize("raw", [b"[not-a-mapping]\n", b"\xff\xfe", b"models: []\nmodels: []\n"])
def test_invalid_catalog_is_a_clean_failure(tmp_path, monkeypatch, raw):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    (home / "registry" / "models.alpha.generated.yaml").write_bytes(raw)
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 3
    assert rust.stdout == ""


def test_provenance_control_characters_are_sanitized(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    path = _write_catalog(home, "alpha", date.today())
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "https://example.test/catalog", '"https://example.test/\\u001b[31m"'
        ),
        encoding="utf-8",
    )
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout
    assert "\x1b" not in rust.stdout


@pytest.mark.parametrize("updated", ["20261109", "2026-W46-1", "2026W461", "2026-W46", "2026W46"])
def test_compact_and_week_dates_match_python(tmp_path, monkeypatch, updated):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    _write_catalog(home, "alpha", updated)
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout


@pytest.mark.parametrize("updated", ["2026-W1", "2026W1"])
def test_partial_week_date_is_unknown_in_both_implementations(tmp_path, monkeypatch, updated):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    _write_catalog(home, "alpha", updated)
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout
    assert "newest unknown" in rust.stdout


def test_bidi_provenance_is_not_printed_raw(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    path = _write_catalog(home, "alpha", date.today())
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "https://example.test/catalog", '"https://example.test/\\u202eoverride"'
        ),
        encoding="utf-8",
    )
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout
    assert "\u202e" not in rust.stdout


def test_empty_source_url_is_omitted_like_python(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    _write_catalog(home, "alpha", date.today(), source='""')
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout
    assert "source=" not in rust.stdout


def test_timestamp_is_treated_as_unknown_date_without_crashing(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    path = _write_catalog(home, "alpha", date.today())
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f'"{date.today().isoformat()}"', "2026-11-09T00:00:00Z"
        ),
        encoding="utf-8",
    )
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout == python.stdout
    assert "newest unknown" in rust.stdout


def test_generated_catalog_symlink_is_rejected(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    outside = tmp_path / "outside.yaml"
    outside.write_text("provenance:\n  source_url: secret://outside\n", encoding="utf-8")
    try:
        os.symlink(outside, home / "registry" / "models.alpha.generated.yaml")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 3
    assert "secret://outside" not in python.output + rust.stdout + rust.stderr
    assert rust.stdout == ""


@pytest.mark.skipif(os.name == "nt", reason="control-character filenames are not valid on Windows")
def test_generated_catalog_provider_name_cannot_inject_terminal_control(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    path = home / "registry" / "models.bad\x1b[31m.generated.yaml"
    path.write_text("models: []\n", encoding="utf-8")
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 3
    assert "\x1b" not in python.output + rust.stdout + rust.stderr


@pytest.mark.skipif(os.name == "nt", reason="raw-byte filenames are Unix-specific")
def test_generated_catalog_invalid_utf8_filename_fails_closed(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    raw_path = os.fsencode(home / "registry") + b"/models.bad\xff.generated.yaml"
    fd = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(b"models: []\n")
    python = _python_status(home, monkeypatch)
    rust = _rust_status(home)
    assert python.exit_code == rust.returncode == 3
    assert rust.stdout == ""


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO unavailable")
def test_generated_catalog_fifo_is_rejected_without_blocking(tmp_path, monkeypatch):
    home = tmp_path / "agentrouter"
    (home / "registry").mkdir(parents=True)
    os.mkfifo(home / "registry" / "models.alpha.generated.yaml")
    monkeypatch.setenv("AGENTROUTER_HOME", str(home))
    python = subprocess.run(
        [sys.executable, "-m", "agentrouter", "providers", "status"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    rust = _rust_status(home, timeout=5)
    assert python.returncode == rust.returncode == 3
    assert rust.stdout == ""
