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
