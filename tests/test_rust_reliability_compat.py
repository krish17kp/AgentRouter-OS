"""Differential coverage for the Rust load and soak report model."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from agentrouter.reliability import LoadOutcome, LoadSpec, run_load, serve_app
from agentrouter.reliability.soak import Sample, SoakResult

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust(request: dict) -> dict:
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "reliability_from_json",
            "-p",
            "agentrouter-reliability",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)["value"]


def test_rust_load_summary_matches_python_fields_and_percentiles():
    outcome = LoadOutcome(
        statuses=Counter({200: 8, 500: 1}),
        transport_errors=Counter({"timeout": 1}),
        latencies_ms=[1.0, 2.0, 3.0, 4.0],
        elapsed_seconds=2.0,
        request_ids=["a", "a", "b"],
    )
    expected = json.loads(json.dumps(outcome.as_dict()))
    assert _rust({"operation": "summarize_load", "outcome": outcome.__dict__}) == expected


def test_rust_soak_summary_and_growth_match_python():
    result = SoakResult(
        samples=[
            Sample(1.0, 10, 4, 100, 0, 4, 0),
            Sample(2.0, 15, 5, 250, 2, 6, 1),
        ],
        total_ok=10,
        total_server_errors=1,
        transport_errors={"timeout": 2},
    )
    assert result.growth("rss_kb") == (10, 15, 1.5)
    assert _rust({"operation": "summarize_soak", "result": result.as_dict()}) == result.as_dict()


def test_rust_load_runner_exercises_real_loopback_and_records_request_ids(home):
    with serve_app(home) as app:
        python = run_load(
            app.url,
            LoadSpec(
                total=12,
                workers=3,
                request=lambda _index: ("GET", "/health", None),
            ),
        )
        rust = _rust(
            {
                "operation": "run_load",
                "url": app.url,
                "total": 12,
                "workers": 3,
                "timeout_seconds": 5,
                "request": {"method": "GET", "path": "/health"},
            }
        )

    assert rust["requests"] == 12
    assert rust["statuses"] == {"200": 12}
    assert rust["transport_errors"] == {}
    assert rust["unexpected_statuses"] == {}
    assert rust["server_errors"] == 0
    assert rust["distinct_request_ids"] == 12
    assert python.statuses == {200: 12}
    assert len(set(python.request_ids)) == 12
    assert set(rust["timing_indicative_only"]) == {
        "elapsed_seconds",
        "throughput_per_second",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "mean_ms",
    }


def test_rust_reliability_harness_starts_and_stops_its_local_api(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    outcome = _rust(
        {
            "operation": "serve_and_load",
            "home": str(tmp_path / "rust-home"),
            "total": 12,
            "workers": 3,
            "timeout_seconds": 5,
        }
    )

    assert outcome["requests"] == 12
    assert outcome["statuses"] == {"200": 12}
    assert outcome["transport_errors"] == {}
    assert outcome["unexpected_statuses"] == {}
    assert outcome["server_errors"] == 0
    assert outcome["distinct_request_ids"] == 12


def test_rust_cli_runs_a_local_soak_and_writes_the_report(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_API_KEY", "test-key-that-must-not-be-used")
    home = tmp_path / "soak-home"
    home.mkdir()
    config = home / "config.yaml"
    config.write_text("user_setting: preserve-me\n", encoding="utf-8")
    report_path = tmp_path / "reports" / "soak.json"
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "agentrouter",
            "--",
            "reliability",
            "soak",
            "--seconds",
            "0.5",
            "--workers",
            "2",
            "--batch",
            "3",
            "--home",
            str(home),
            "--out",
            str(report_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert json.loads(report_path.read_text(encoding="utf-8")) == result
    assert result["cycles"] >= 1
    assert result["total_ok"] > 0
    assert result["total_server_errors"] == 0
    assert result["transport_errors"] == {}
    assert sum(sample["ok"] for sample in result["samples"]) == result["total_ok"]
    assert config.read_text(encoding="utf-8") == "user_setting: preserve-me\n"
    assert "SOAK OK:" in process.stderr


def test_rust_cli_reports_a_home_initialization_failure(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    invalid_home = tmp_path / "file-instead-of-home"
    invalid_home.write_text("preserve this file", encoding="utf-8")
    process = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "agentrouter-cli",
            "--bin",
            "agentrouter",
            "--",
            "reliability",
            "soak",
            "--seconds",
            "0",
            "--home",
            str(invalid_home),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )

    assert process.returncode == 1
    assert "could not initialise a soak home" in process.stderr
    assert invalid_home.read_text(encoding="utf-8") == "preserve this file"


def test_rust_load_runner_does_not_follow_redirects():
    redirect_target_hit = threading.Event()

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            redirect_target_hit.set()
            self.send_response(200)
            self.end_headers()

        def log_message(self, _format, *_args):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/redirect-target")
            self.end_headers()

        def log_message(self, _format, *_args):
            pass

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    redirect_thread = threading.Thread(target=redirect.serve_forever, daemon=True)
    target_thread.start()
    redirect_thread.start()
    try:
        rust = _rust(
            {
                "operation": "run_load",
                "url": f"http://127.0.0.1:{redirect.server_port}",
                "total": 1,
                "workers": 1,
                "timeout_seconds": 5,
                "request": {"method": "GET", "path": "/redirect"},
            }
        )
    finally:
        redirect.shutdown()
        target.shutdown()
        redirect.server_close()
        target.server_close()
        redirect_thread.join(timeout=2)
        target_thread.join(timeout=2)

    assert rust["statuses"] == {"302": 1}
    assert rust["unexpected_statuses"] == {"302": 1}
    assert not redirect_target_hit.is_set()


def test_rust_soak_runs_batches_and_reports_resource_samples(home):
    with serve_app(home) as app:
        result = _rust(
            {
                "operation": "soak",
                "url": app.url,
                "home": str(home),
                "seconds": 0.02,
                "workers": 1,
                "batch": 1,
            }
        )

    assert result["cycles"] >= 1
    assert len(result["samples"]) == result["cycles"]
    assert result["total_ok"] == sum(sample["ok"] for sample in result["samples"])
    assert result["total_server_errors"] == sum(
        sample["server_errors"] for sample in result["samples"]
    )
    assert set(result["resource_trend_indicative_only"]) == {"rss_kb", "open_fds", "db_bytes"}
