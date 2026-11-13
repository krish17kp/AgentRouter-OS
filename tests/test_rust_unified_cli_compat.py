"""Smoke and dispatch checks for the unified Rust `agentrouter` executable."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

from agentrouter.annotation import candidates as candidate_mod
from agentrouter.annotation import store

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def unified_binary():
    built = subprocess.run(
        ["cargo", "build", "--workspace", "--locked"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target"))
    binary = target / "debug" / "agentrouter"
    if os.name == "nt":
        binary = binary.with_suffix(".exe")
    assert binary.exists()
    return binary


def _run(binary, *args: str, home: Path | None = None):
    env = os.environ.copy()
    if home is not None:
        env["AGENTROUTER_HOME"] = str(home)
    return subprocess.run(
        [str(binary), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )


def test_help_and_version_are_available(unified_binary):
    help_result = _run(unified_binary, "--help")
    assert help_result.returncode == 0
    assert "dataset" in help_result.stdout
    assert "route" in help_result.stdout

    version = _run(unified_binary, "--version")
    assert version.returncode == 0
    assert version.stdout.strip() == "agentrouter 0.5.0rc1"


def test_init_and_route_dispatch_to_rust_implementations(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    assert (home / "registry" / "providers.yaml").is_file()

    task = "Review this Python repository for security issues."
    unified_route = _run(unified_binary, "route", task, "--json", home=home)
    direct_route = subprocess.run(
        [
            str(unified_binary.with_name("cli_route_cli" + (".exe" if os.name == "nt" else ""))),
            str(home),
            task,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert unified_route.returncode == direct_route.returncode == 0
    assert json.loads(unified_route.stdout) == json.loads(direct_route.stdout)

    hosts = _run(unified_binary, "hosts", "list", home=home)
    assert hosts.returncode == 0, hosts.stderr
    assert "openai-api" in hosts.stdout

    models = _run(unified_binary, "models", "list", home=home)
    assert models.returncode == 0, models.stderr
    first_model = models.stdout.splitlines()[0].split()[0]
    shown = _run(unified_binary, "models", "show", first_model, home=home)
    assert shown.returncode == 0, shown.stderr
    assert "execution targets:" in shown.stdout

    saved_route = _run(unified_binary, "route", task, "--save", "--json", home=home)
    assert saved_route.returncode == 0, saved_route.stderr
    decision_id = json.loads(saved_route.stdout)["decision_id"]
    feedback = _run(
        unified_binary,
        "feedback",
        decision_id,
        "--rating",
        "4",
        "--note",
        "test outcome",
        home=home,
    )
    assert feedback.returncode == 0, feedback.stderr
    assert "Recorded rating 4" in feedback.stdout

    stats = _run(unified_binary, "stats", "--json", home=home)
    assert stats.returncode == 0, stats.stderr
    aggregate = json.loads(stats.stdout)
    assert aggregate["decisions"] == 1
    assert aggregate["feedback"] == {
        "count": 1,
        "avg_rating": 4.0,
        "acceptance_rate": 1.0,
    }
    stats_text = _run(unified_binary, "stats", home=home)
    assert stats_text.returncode == 0, stats_text.stderr
    assert "Decisions logged: 1" in stats_text.stdout
    assert "Feedback: 1 rating(s), avg 4" in stats_text.stdout


def test_dataset_is_available_from_unified_entrypoint(tmp_path, unified_binary):
    candidates_path = tmp_path / "candidate-pool.yaml"
    generated = _run(
        unified_binary,
        "dataset",
        "gen-candidates",
        "--out",
        candidates_path,
        "--count",
        "20",
        "--seed",
        "-901",
    )
    assert generated.returncode == 0, generated.stderr
    assert store.load_candidates(candidates_path) == candidate_mod.generate(20, seed=-901)


def test_provider_catalog_rollback_is_reversible(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    registry = home / "registry"
    catalog = registry / "models.fixture.generated.yaml"
    original = (
        b"provenance: {source_url: https://fixture.invalid}\n"
        b"models:\n"
        b"  - provider: openrouter\n"
        b"    model_id: fixture/model\n"
        b"    context_window: 8192\n"
        b"    max_output_tokens: 2048\n"
        b"    pricing_tier: low\n"
        b"    latency_tier: medium\n"
        b"    ability: {coding: 6, reasoning: 6, writing: 6}\n"
        b"    tool_support: []\n"
        b"    vision_support: false\n"
        b"    deprecation_status: active\n"
    )
    catalog.write_bytes(original)

    rolled_back = _run(unified_binary, "providers", "rollback", "fixture", home=home)
    assert rolled_back.returncode == 0, rolled_back.stderr
    assert not catalog.exists()
    assert catalog.with_name(catalog.name + ".bak").read_bytes() == original

    restored = _run(unified_binary, "providers", "restore", "fixture", home=home)
    assert restored.returncode == 0, restored.stderr
    assert catalog.read_bytes() == original
    assert not catalog.with_name(catalog.name + ".bak").exists()

    doctor = _run(unified_binary, "providers", "doctor", home=home)
    assert doctor.returncode == 0, doctor.stderr
    assert "[STALE]" in doctor.stdout

    catalog.write_text("models: [\n", encoding="utf-8")
    broken = _run(unified_binary, "providers", "doctor", home=home)
    assert broken.returncode == 3
    assert "[FAIL ] fixture" in broken.stdout


def test_provider_refresh_preflight_is_offline_and_hides_provider_credentials(
    tmp_path, unified_binary, monkeypatch
):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    unsupported = _run(unified_binary, "providers", "refresh", "cursor", home=home)
    assert unsupported.returncode == 2
    assert "not refreshable" in unsupported.stderr
    assert "openrouter, openai" in unsupported.stderr

    missing_key = _run(unified_binary, "providers", "refresh", "openai", home=home)
    assert missing_key.returncode == 1
    assert "OPENAI_API_KEY" in missing_key.stdout + missing_key.stderr
    assert "registry was NOT modified" in missing_key.stderr
    assert not (home / "registry" / "models.openai.generated.yaml").exists()

    invalid_limit = _run(
        unified_binary, "providers", "refresh", "openrouter", "--limit", "0", home=home
    )
    assert invalid_limit.returncode == 2


def test_server_and_mcp_are_available_from_unified_entrypoint(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr

    server_help = _run(unified_binary, "server", "--help", home=home)
    assert server_help.returncode == 0, server_help.stderr
    assert "agentrouter server" in server_help.stdout

    mcp_help = _run(unified_binary, "mcp", "--help", home=home)
    assert mcp_help.returncode == 0, mcp_help.stderr
    assert "stdio server" in mcp_help.stdout

    invalid_server = _run(unified_binary, "server", "--port", "70000", home=home)
    assert invalid_server.returncode == 2
    assert "0 to 65535" in invalid_server.stderr
    invalid_mcp = _run(unified_binary, "mcp", "--unexpected", home=home)
    assert invalid_mcp.returncode == 2


def test_unified_mcp_serves_protocol_over_stdio(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    requests = (
        '{"jsonrpc":"2.0","id":1,"method":"initialize",'
        '"params":{"protocolVersion":"2025-11-25"}}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
    )
    result = subprocess.run(
        [str(unified_binary), "mcp"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=requests,
        env={**os.environ, "AGENTROUTER_HOME": str(home)},
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert responses[0]["result"]["protocolVersion"] == "2025-11-25"
    assert [tool["name"] for tool in responses[1]["result"]["tools"]] == [
        "route",
        "classify",
        "explain",
        "list_models",
        "list_hosts",
    ]


def test_unified_server_starts_http_api_and_shuts_down(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    process = subprocess.Popen(
        [str(unified_binary), "server", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "AGENTROUTER_HOME": str(home)},
        **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}),
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                pytest.fail(f"HTTP server exited early: {stderr}")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=0.5
                ) as response:
                    assert response.status == 200
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(0.05)
        else:
            pytest.fail("HTTP server did not become healthy within 10 seconds")
    finally:
        if process.poll() is None:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_unified_execute_revalidates_safety_and_requires_confirmation(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    routed = _run(
        unified_binary,
        "route",
        "write a short haiku about routers",
        "--save",
        "--json",
        home=home,
    )
    assert routed.returncode == 0, routed.stderr
    payload = json.loads(routed.stdout)
    provider_file = home / "registry" / "providers.yaml"
    provider_data = yaml.safe_load(provider_file.read_text(encoding="utf-8"))
    provider = next(
        item
        for item in provider_data["providers"]
        if item["id"] == payload["recommendation"]["provider"]
    )
    marker = tmp_path / "must-not-exist"
    provider["supports_execution"] = True
    provider["exec_command"] = [
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(marker)!r}).touch()",
    ]
    provider_file.write_text(yaml.safe_dump(provider_data), encoding="utf-8")

    preview = _run(
        unified_binary, "execute", payload["decision_id"], "--dry-run", "--yes", home=home
    )
    assert preview.returncode == 0, preview.stderr
    assert "Dry run: nothing executed." in preview.stdout
    assert not marker.exists()

    unconfirmed = _run(unified_binary, "execute", payload["decision_id"], home=home)
    assert unconfirmed.returncode == 2
    assert "--yes" in unconfirmed.stdout
    assert not marker.exists()

    approved = _run(unified_binary, "execute", payload["decision_id"], "--yes", home=home)
    assert approved.returncode == 0, approved.stderr
    assert marker.exists()


def test_unified_execute_never_runs_high_risk_decisions(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    routed = _run(
        unified_binary,
        "route",
        "rotate the production auth credentials and deploy",
        "--save",
        "--json",
        home=home,
    )
    assert routed.returncode == 0, routed.stderr
    payload = json.loads(routed.stdout)
    assert payload["classification"]["risk"] == "high"
    provider_file = home / "registry" / "providers.yaml"
    provider_data = yaml.safe_load(provider_file.read_text(encoding="utf-8"))
    for provider in provider_data["providers"]:
        provider["supports_execution"] = True
        provider["exec_command"] = [sys.executable, "-c", "print('MUST_NOT_RUN')"]
    provider_file.write_text(yaml.safe_dump(provider_data), encoding="utf-8")

    blocked = _run(unified_binary, "execute", payload["decision_id"], "--yes", home=home)
    assert blocked.returncode == 2
    assert "Execution blocked" in blocked.stderr
    assert "MUST_NOT_RUN" not in blocked.stdout

    # Tampering with the persisted gate must also fail closed after a route.
    import sqlite3

    database = sqlite3.connect(home / "agentrouter.db")
    row = database.execute(
        "SELECT payload FROM decisions WHERE id = ?",
        (int(payload["decision_id"].split("_")[1]),),
    ).fetchone()
    tampered = json.loads(row[0])
    tampered["gates"]["auto_execute_allowed"] = True
    database.execute(
        "UPDATE decisions SET payload = ? WHERE id = ?",
        (json.dumps(tampered), int(payload["decision_id"].split("_")[1])),
    )
    database.commit()
    database.close()
    changed_gate = _run(unified_binary, "execute", payload["decision_id"], "--yes", home=home)
    assert changed_gate.returncode == 2
    assert "safety gate changed" in changed_gate.stderr
    assert "MUST_NOT_RUN" not in changed_gate.stdout


def test_unknown_or_unported_command_fails_with_usage(unified_binary):
    result = _run(unified_binary, "plugin")
    assert result.returncode == 2
    assert "not-yet-ported" in result.stderr
    assert "dataset" in result.stderr
