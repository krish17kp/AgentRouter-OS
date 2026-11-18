"""Rust seed-home probe matches Python's `agentrouter init` behavior."""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess

import pytest
from typer.testing import CliRunner

from agentrouter.cli import app

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
runner = CliRunner()


def _rust_init(home, *options, check=True):
    return subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "init_cli", "--", str(home), *options],
        cwd="rust/agentrouter-cli",
        capture_output=True,
        text=True,
        timeout=120,
        check=check,
    )


def _tables(home):
    with sqlite3.connect(home / "agentrouter.db") as conn:
        return {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }


def test_rust_init_matches_python_seed_and_is_idempotent(tmp_path, monkeypatch):
    python_home = tmp_path / "python"
    rust_home = tmp_path / "rust"
    monkeypatch.setenv("AGENTROUTER_HOME", str(python_home))

    first_python = runner.invoke(app, ["init"])
    first_rust = _rust_init(rust_home)
    assert first_python.exit_code == 0, first_python.output
    assert first_rust.stdout.replace(str(rust_home), "<HOME>") == first_python.stdout.replace(
        str(python_home), "<HOME>"
    )
    for relative in ("config.yaml", "registry/providers.yaml", "registry/models.yaml"):
        assert (rust_home / relative).read_bytes() == (python_home / relative).read_bytes()
    assert {"decisions", "feedback"}.issubset(_tables(rust_home))

    second_python = runner.invoke(app, ["init"])
    second_rust = _rust_init(rust_home)
    assert second_python.exit_code == 0, second_python.output
    assert second_rust.stdout.replace(str(rust_home), "<HOME>") == second_python.stdout.replace(
        str(python_home), "<HOME>"
    )


def test_rust_force_init_backs_up_edits_and_reseeds_like_python(tmp_path, monkeypatch):
    python_home = tmp_path / "python"
    rust_home = tmp_path / "rust"
    monkeypatch.setenv("AGENTROUTER_HOME", str(python_home))
    assert runner.invoke(app, ["init"]).exit_code == 0
    _rust_init(rust_home)
    for home in (python_home, rust_home):
        (home / "config.yaml").write_text("# custom config\n", encoding="utf-8")
        (home / "registry" / "models.yaml").write_text("# custom models\n", encoding="utf-8")

    python = runner.invoke(app, ["init", "--force"])
    rust = _rust_init(rust_home, "--force")
    assert python.exit_code == rust.returncode == 0
    assert rust.stdout.replace(str(rust_home), "<HOME>") == python.stdout.replace(
        str(python_home), "<HOME>"
    )
    for relative in ("config.yaml", "registry/providers.yaml", "registry/models.yaml"):
        assert (rust_home / relative).read_bytes() == (python_home / relative).read_bytes()
        backup = relative + ".bak"
        assert (rust_home / backup).read_bytes() == (python_home / backup).read_bytes()
        if os.name != "nt":
            assert (rust_home / backup).stat().st_mode & 0o777 == (
                python_home / backup
            ).stat().st_mode & 0o777


def test_rust_force_init_refuses_linked_seed_target(tmp_path):
    home = tmp_path / "agentrouter"
    _rust_init(home)
    outside = tmp_path / "outside.yaml"
    outside.write_text("keep me\n", encoding="utf-8")
    target = home / "config.yaml"
    target.unlink()
    try:
        os.symlink(outside, target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    result = _rust_init(home, "--force", check=False)
    assert result.returncode == 3
    assert result.stdout == ""
    assert outside.read_text(encoding="utf-8") == "keep me\n"


def test_rust_init_refuses_linked_registry_directory(tmp_path):
    home = tmp_path / "agentrouter"
    outside = tmp_path / "outside"
    home.mkdir()
    outside.mkdir()
    try:
        os.symlink(outside, home / "registry", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlink creation unavailable")
    for options in ((), ("--force",)):
        result = _rust_init(home, *options, check=False)
        assert result.returncode == 3
        assert result.stdout == ""
        assert not list(outside.iterdir())


def test_rust_init_refuses_linked_database_target(tmp_path):
    home = tmp_path / "agentrouter"
    home.mkdir()
    outside = tmp_path / "outside.db"
    with sqlite3.connect(outside) as conn:
        conn.execute("CREATE TABLE sentinel (id INTEGER)")
    try:
        os.symlink(outside, home / "agentrouter.db")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    result = _rust_init(home, check=False)
    assert result.returncode == 3
    with sqlite3.connect(outside) as conn:
        tables = [
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        ]
    assert tables == ["sentinel"]


def test_rust_init_refuses_hard_linked_database_target(tmp_path):
    home = tmp_path / "agentrouter"
    home.mkdir()
    outside = tmp_path / "outside.db"
    with sqlite3.connect(outside) as conn:
        conn.execute("CREATE TABLE sentinel (id INTEGER)")
    try:
        os.link(outside, home / "agentrouter.db")
    except (OSError, NotImplementedError):
        pytest.skip("hard link creation unavailable")
    result = _rust_init(home, check=False)
    assert result.returncode == 3
    with sqlite3.connect(outside) as conn:
        tables = [
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        ]
    assert tables == ["sentinel"]


def test_rust_force_init_replaces_hard_links_without_touching_outside_files(tmp_path):
    home = tmp_path / "agentrouter"
    _rust_init(home)
    outside_seed = tmp_path / "outside-seed.yaml"
    outside_backup = tmp_path / "outside-backup.yaml"
    outside_seed.write_text("outside seed\n", encoding="utf-8")
    outside_backup.write_text("outside backup\n", encoding="utf-8")
    target = home / "config.yaml"
    target.unlink()
    try:
        os.link(outside_seed, target)
        os.link(outside_backup, home / "config.yaml.bak")
    except (OSError, NotImplementedError):
        pytest.skip("hard link creation unavailable")
    result = _rust_init(home, "--force")
    assert result.returncode == 0
    assert outside_seed.read_text(encoding="utf-8") == "outside seed\n"
    assert outside_backup.read_text(encoding="utf-8") == "outside backup\n"
    assert (home / "config.yaml.bak").read_text(encoding="utf-8") == "outside seed\n"
    assert target.read_text(encoding="utf-8") != "outside seed\n"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_rust_force_init_preserves_existing_file_modes_like_python(tmp_path, monkeypatch):
    python_home = tmp_path / "python"
    rust_home = tmp_path / "rust"
    monkeypatch.setenv("AGENTROUTER_HOME", str(python_home))
    assert runner.invoke(app, ["init"]).exit_code == 0
    _rust_init(rust_home)
    for home in (python_home, rust_home):
        (home / "config.yaml").chmod(0o640)
        backup = home / "config.yaml.bak"
        backup.write_text("prior backup\n", encoding="utf-8")
        backup.chmod(0o600)
    assert runner.invoke(app, ["init", "--force"]).exit_code == 0
    _rust_init(rust_home, "--force")
    for relative in ("config.yaml", "config.yaml.bak"):
        assert (rust_home / relative).stat().st_mode & 0o777 == (
            python_home / relative
        ).stat().st_mode & 0o777


@pytest.mark.parametrize("option", ["--unknown", "--force --extra"])
def test_rust_init_rejects_unknown_options(tmp_path, option):
    result = _rust_init(tmp_path / "agentrouter", *option.split(), check=False)
    assert result.returncode == 2
    assert result.stdout == ""
