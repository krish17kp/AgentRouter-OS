"""Contract checks for the Rust structured diagnostics probe."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _init(home):
    return subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "init_cli", "--", str(home)],
        cwd="rust/agentrouter-cli",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _doctor(home, *args, env=None):
    process_env = os.environ.copy()
    process_env.pop("AGENTROUTER_API_KEY", None)
    process_env.pop("OPENAI_API_KEY", None)
    if env:
        process_env.update(env)
    return subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--bin", "doctor_cli", "--", str(home), *args],
        cwd="rust/agentrouter-cli",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=process_env,
    )


def test_json_report_has_stable_ids_and_check_shape(tmp_path):
    home = tmp_path / "agentrouter"
    home.mkdir()
    initialized = _init(home)
    assert initialized.returncode == 0, initialized.stderr
    result = _doctor(home, "--json")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] in {"ok", "warn", "fail"}
    checks = payload["checks"]
    ids = [check["id"] for check in checks]
    assert len(ids) == len(set(ids))
    assert {
        "app.version",
        "runtime.rust",
        "data.home",
        "data.database",
        "registry.load",
        "catalogs.generated",
        "hosts.ready",
        "server.auth",
        "contract.version",
        "observability.logging",
    } <= set(ids)
    assert all(set(check) == {"id", "status", "summary", "remedy"} for check in checks)
    assert all(check["status"] in {"ok", "warn", "fail"} for check in checks)
    assert all(check["remedy"] for check in checks if check["status"] != "ok")


def test_broken_registry_is_reported_without_echoing_file_content(tmp_path):
    home = tmp_path / "agentrouter"
    registry = home / "registry"
    registry.mkdir(parents=True)
    secret = "sk-livekey0123456789abcdefghij"
    (registry / "providers.yaml").write_text(f'token: "{secret}\n', encoding="utf-8")
    result = _doctor(home, "--json")
    payload = json.loads(result.stdout)
    check = next(item for item in payload["checks"] if item["id"] == "registry.load")
    assert result.returncode == 1
    assert check["status"] == "fail"
    assert check["remedy"]
    assert secret not in result.stdout + result.stderr


def test_corrupt_database_does_not_hide_other_checks(tmp_path):
    home = tmp_path / "agentrouter"
    home.mkdir()
    (home / "agentrouter.db").write_bytes(b"not a sqlite database")
    result = _doctor(home, "--json")
    payload = json.loads(result.stdout)
    checks = {item["id"]: item for item in payload["checks"]}
    assert result.returncode == 1
    assert checks["data.database"]["status"] == "fail"
    assert "registry.load" in checks
    assert "contract.version" in checks


def test_api_secrets_are_never_printed_and_usage_is_opt_in(tmp_path):
    home = tmp_path / "agentrouter"
    home.mkdir()
    secret = "sk-livekey0123456789abcdefghij"
    ordinary = _doctor(
        home, "--json", env={"AGENTROUTER_API_KEY": secret, "OPENAI_API_KEY": secret}
    )
    assert secret not in ordinary.stdout + ordinary.stderr
    assert "usage.openai-api" not in ordinary.stdout
    live = _doctor(home, "--verify-live", "--json", env={"OPENAI_API_KEY": secret})
    assert secret not in live.stdout + live.stderr
    payload = json.loads(live.stdout)
    usage = next(item for item in payload["checks"] if item["id"] == "usage.openai-api")
    assert usage["status"] == "ok"
    assert "unsupported" in usage["summary"]


def test_missing_home_is_a_failure_but_report_is_complete(tmp_path):
    result = _doctor(tmp_path / "missing", "--json")
    payload = json.loads(result.stdout)
    checks = {item["id"]: item for item in payload["checks"]}
    assert result.returncode == 1
    assert checks["data.home"]["status"] == "fail"
    assert "registry.load" in checks
    assert "observability.logging" in checks


def _bundle_text(directory):
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in directory.iterdir()
        if path.suffix in {".json", ".txt"}
    )


def test_bundle_is_allowlisted_and_withholds_secret_and_task_text(tmp_path):
    from agentrouter import store

    home = tmp_path / "agentrouter"
    initialized = _init(home)
    assert initialized.returncode == 0, initialized.stderr
    secret = "sk-livekey0123456789abcdefghij"
    task = "CONFIDENTIAL-ROUTED-TASK-99631"
    (home / ".env").write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
    (home / "credentials.json").write_text(json.dumps({"key": secret}), encoding="utf-8")
    conn = store.connect(home)
    try:
        store.save_decision(conn, task, {"prompt": "PRIVATE-PROMPT-718"})
    finally:
        conn.close()

    destination = tmp_path / "bundle"
    result = _doctor(
        home,
        "--json",
        "--bundle",
        str(destination),
        env={
            "AGENTROUTER_API_KEY": secret,
            "AGENTROUTER_USER": "PRIVATE-USER-IDENTIFIER-931",
            "AGENTROUTER_LOG": "PRIVATE-LOG-PATH-482",
        },
    )
    assert result.returncode == 0, result.stderr
    assert {path.name for path in destination.iterdir()} == {
        "doctor.json",
        "environment.json",
        "data-shape.json",
        "README.txt",
    }
    contents = _bundle_text(destination)
    assert secret not in contents
    assert "PRIVATE-USER-IDENTIFIER-931" not in contents
    assert "PRIVATE-LOG-PATH-482" not in contents
    assert task not in contents
    assert "PRIVATE-PROMPT-718" not in contents
    environment = json.loads((destination / "environment.json").read_text(encoding="utf-8"))
    assert environment["settings"]["AGENTROUTER_API_KEY"] == "set (value withheld)"
    assert environment["settings"]["AGENTROUTER_USER"] == "set (value withheld)"
    assert environment["settings"]["AGENTROUTER_LOG"] == "set (value withheld)"
    shape = json.loads((destination / "data-shape.json").read_text(encoding="utf-8"))
    assert shape["decisions"] == 1


def test_bundle_database_is_opt_in_snapshot_with_task_text_warning(tmp_path):
    import sqlite3

    from agentrouter import store

    home = tmp_path / "agentrouter"
    assert _init(home).returncode == 0
    task = "TASK-ONLY-IN-OPT-IN-DB"
    conn = store.connect(home)
    try:
        store.save_decision(conn, task, {"prompt": "snapshot body"})
    finally:
        conn.close()

    destination = tmp_path / "bundle-with-db"
    result = _doctor(home, "--bundle", str(destination), "--include-database")
    assert result.returncode == 0, result.stderr
    assert (destination / "decisions.db").is_file()
    readme = (destination / "README.txt").read_text(encoding="utf-8")
    assert "INCLUDING task text" in readme
    assert "Review it before sharing" in readme
    copied = sqlite3.connect(f"file:{destination / 'decisions.db'}?mode=ro", uri=True)
    try:
        assert copied.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1
        assert copied.execute("SELECT task FROM decisions").fetchone()[0] == task
    finally:
        copied.close()


def test_bundle_refuses_existing_destination_without_overwriting(tmp_path):
    home = tmp_path / "agentrouter"
    assert _init(home).returncode == 0
    destination = tmp_path / "existing-bundle"
    destination.mkdir()
    keep = destination / "keep.txt"
    keep.write_text("keep this", encoding="utf-8")
    result = _doctor(home, "--bundle", str(destination))
    assert result.returncode == 2
    assert keep.read_text(encoding="utf-8") == "keep this"


@pytest.mark.skipif(os.name == "nt", reason="directory symlink privilege varies on Windows")
def test_bundle_refuses_symlink_destination_without_touching_target(tmp_path):
    home = tmp_path / "agentrouter"
    assert _init(home).returncode == 0
    target = tmp_path / "preserved"
    target.mkdir()
    keep = target / "keep.txt"
    keep.write_text("preserve me", encoding="utf-8")
    destination = tmp_path / "bundle-link"
    destination.symlink_to(target, target_is_directory=True)
    result = _doctor(home, "--bundle", str(destination))
    assert result.returncode == 2
    assert keep.read_text(encoding="utf-8") == "preserve me"
