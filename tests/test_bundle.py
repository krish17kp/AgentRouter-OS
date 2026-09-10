"""Diagnostic bundle safety (TASK-018C).

A bundle is something a user hands to someone else, so the threat model is
inverted: the danger is not collecting too little, it is collecting something we
should not have. Every test here is an attempt to get something into the bundle
that must never be there.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from agentrouter import bundle, store
from agentrouter.cli import app

runner = CliRunner()
API_KEY = "sk-livekey0123456789abcdefghij"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    monkeypatch.setenv("AGENTROUTER_HOME", str(h))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    assert runner.invoke(app, ["init"]).exit_code == 0
    return h


def _text(directory) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in directory.iterdir()
        if p.suffix in (".json", ".txt")
    )


def test_a_dotenv_beside_the_data_is_never_collected(home, tmp_path):
    """The single most dangerous thing a directory scan would pick up."""
    (home / ".env").write_text(f"OPENAI_API_KEY={API_KEY}\n", encoding="utf-8")
    (home / "credentials.json").write_text(json.dumps({"key": API_KEY}), encoding="utf-8")

    written = bundle.create(home, tmp_path / "b")

    assert ".env" not in written.files
    assert "credentials.json" not in written.files
    assert API_KEY not in _text(written.directory)


def test_the_api_key_value_is_never_recorded(home, tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_API_KEY", API_KEY)
    written = bundle.create(home, tmp_path / "b")
    body = _text(written.directory)
    assert API_KEY not in body
    assert "value withheld" in body


def test_a_blank_api_key_is_reported_as_blank_not_as_set(home, tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_API_KEY", "   ")
    written = bundle.create(home, tmp_path / "b")
    settings = json.loads((written.directory / "environment.json").read_text())["settings"]
    assert settings["AGENTROUTER_API_KEY"] == "set but blank"


def test_task_text_is_not_collected_without_the_database(home, tmp_path):
    """The decision log holds what the user actually routed."""
    conn = store.connect(home)
    try:
        store.save_decision(conn, "MY-CONFIDENTIAL-TASK-TEXT", {"prompt": "SECRET-PROMPT"})
    finally:
        conn.close()

    written = bundle.create(home, tmp_path / "b")
    body = _text(written.directory)
    assert "MY-CONFIDENTIAL-TASK-TEXT" not in body
    assert "SECRET-PROMPT" not in body
    # ...but the shape is reported, which is what a diagnosis needs
    shape = json.loads((written.directory / "data-shape.json").read_text())
    assert shape["decisions"] == 1


def test_including_the_database_uses_a_snapshot_not_a_file_copy(home, tmp_path):
    """A filesystem copy of a WAL database silently yields an EMPTY log, which
    would make the bundle worse than useless (measured in TASK-018B)."""
    import sqlite3

    conn = store.connect(home)
    try:
        for i in range(5):
            store.save_decision(conn, f"task {i}", {"n": i})

        written = bundle.create(home, tmp_path / "b", include_database=True)
        assert "decisions.db" in written.files

        copied = sqlite3.connect(f"file:{written.directory / 'decisions.db'}?mode=ro", uri=True)
        try:
            assert copied.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 5
        finally:
            copied.close()
    finally:
        conn.close()


def test_including_the_database_warns_that_it_contains_task_text(home, tmp_path):
    """Opting in must be informed, since the log holds what the user routed."""
    written = bundle.create(home, tmp_path / "b", include_database=True)
    readme = (written.directory / "README.txt").read_text()
    assert "INCLUDING task text" in readme
    assert "Review it before sharing" in readme


def test_an_existing_destination_is_refused_not_clobbered(home, tmp_path):
    target = tmp_path / "b"
    target.mkdir()
    (target / "precious.txt").write_text("do not delete me", encoding="utf-8")

    with pytest.raises(bundle.BundleError, match="already exists"):
        bundle.create(home, target)
    assert (target / "precious.txt").read_text() == "do not delete me"


def test_a_symlinked_destination_is_refused(home, tmp_path):
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(victim, target_is_directory=True)

    with pytest.raises(bundle.BundleError):
        bundle.create(home, link)
    assert (victim / "keep.txt").read_text() == "keep"


def test_bundle_text_passes_through_redaction(home, tmp_path):
    """Belt and braces: even an allowlisted artifact is redacted."""
    (home / "registry" / "providers.yaml").write_text(
        f'providers:\n  - id: x\n    token: "{API_KEY}\n', encoding="utf-8"
    )
    written = bundle.create(home, tmp_path / "b")
    assert API_KEY not in _text(written.directory)


def test_the_cli_writes_a_bundle_and_names_what_is_inside(home, tmp_path):
    result = runner.invoke(app, ["doctor", "--bundle", str(tmp_path / "b")])
    assert result.exit_code in (0, 1), result.output
    assert "Bundle written to" in result.output
    assert "No .env, credential file or key value is included" in result.output
    assert (tmp_path / "b" / "doctor.json").exists()
