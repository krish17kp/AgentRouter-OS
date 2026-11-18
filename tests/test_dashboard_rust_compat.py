"""Exercise the Rust dashboard server against the installed Python contract."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from agentrouter import store
from agentrouter.dashboard import render_html
from agentrouter.registry import load_all_models, load_providers

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")


def _rust_render_html(stats: dict, recent: list[dict]) -> str:
    root = Path(__file__).resolve().parents[1]
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "dashboard_render_from_json",
        ],
        cwd=root,
        input=json.dumps({"stats": stats, "recent": recent}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return process.stdout


@pytest.mark.parametrize(
    ("stats", "recent"),
    [
        (
            {
                "decisions": 0,
                "by_risk": {},
                "by_pricing_tier": {},
                "feedback": {"count": 0, "avg_rating": None, "acceptance_rate": None},
            },
            [],
        ),
        (
            {
                "decisions": 2,
                "by_risk": {"<high>&": 1, "low": 1},
                "by_pricing_tier": {"medium": 2},
                "by_user": {"krish's & team": 2},
                "feedback": {"count": 1, "avg_rating": 4.0, "acceptance_rate": 0.5},
            },
            [
                {
                    "decision_id": "d'<1>&",
                    "created_at": "2026-07-08T09:00:00+00:00",
                    "user": "<krish>",
                    "task": "🧭 & <review> " + ("x" * 90),
                    "model": "provider/model 'safe'",
                    "score": 0.812,
                    "risk": "<low>",
                }
            ],
        ),
        (
            {
                "decisions": 0,
                "by_risk": {"unknown": 0},
                "by_pricing_tier": {},
                "feedback": {"count": 0, "avg_rating": None, "acceptance_rate": None},
            },
            [],
        ),
    ],
)
def test_rust_dashboard_html_matches_python(stats, recent):
    assert _rust_render_html(stats, recent) == render_html(stats, recent)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_rust_dashboard_serves_loopback_read_only_page(home):
    conn = store.connect(home)
    store.save_decision(
        conn,
        "render the dashboard safely",
        {"recommendation": {"model": "m1", "score": 0.9}, "classification": {"risk": "low"}},
    )
    conn.close()
    conn = store.connect(home)
    before = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    providers = load_providers(home / "registry" / "providers.yaml")
    models, _warnings = load_all_models(home / "registry", providers)
    tier_by_key = {model.key: model.pricing_tier.value for model in models}
    expected_page = render_html(
        store.aggregate_stats(conn, tier_by_key), store.recent_decisions(conn)
    )
    conn.close()
    port = _free_port()
    root = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [
            "cargo",
            "run",
            "--quiet",
            "-p",
            "agentrouter-cli",
            "--bin",
            "dashboard_cli",
            "--",
            str(home),
            str(port),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        url = f"http://127.0.0.1:{port}/"
        page = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.fail(f"Rust dashboard exited early: {stdout}\n{stderr}")
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    page = response.read().decode("utf-8")
                    assert response.status == 200
                    assert response.headers["Content-Type"] == "text/html; charset=utf-8"
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        assert page is not None, "Rust dashboard did not start before the timeout"
        assert page == expected_page
        assert "AgentRouter OS — decision log (read-only)" in page
        assert "render the dashboard safely" in page
        assert "<form" not in page and "<script" not in page

        request = urllib.request.Request(url, data=b"", method="POST")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=2)
        assert error.value.code == 405
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    conn = store.connect(home)
    after = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    conn.close()
    assert after == before
