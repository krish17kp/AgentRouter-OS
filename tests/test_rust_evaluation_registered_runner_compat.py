"""End-to-end differential checks for the registered Rust evaluation runner."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentrouter.evaluation import base as evaluation_base
from agentrouter.evaluation.runner import run as python_run

pytestmark = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not on PATH")
ROOT = Path(__file__).resolve().parents[1]


def _rust_process(request, *, check=True):
    environment = None
    if request.get("measure_all"):
        subprocess.run(
            [
                "cargo",
                "build",
                "--quiet",
                "--locked",
                "-p",
                "agentrouter-cli",
                "--bin",
                "agentrouter",
            ],
            cwd=ROOT,
            timeout=120,
            check=True,
        )
        environment = os.environ.copy()
        target = Path(environment.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
        environment["PATH"] = f"{target}{os.pathsep}{environment.get('PATH', '')}"
    return subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--bin",
            "evaluation_registered_runner_from_json",
            "-p",
            "agentrouter-evaluation",
        ],
        input=json.dumps({"project_root": str(ROOT), **request}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=environment,
        timeout=120,
        check=check,
    )


def _rust_run(request):
    process = _rust_process(request)
    return json.loads(process.stdout)


def _without_runtime_values(report):
    normalized = {key: value for key, value in report.items() if key != "environment"}
    detail = normalized["dimensions"]["performance"]["detail"]
    detail.pop("classify_median_ms")
    detail.pop("route_median_ms")
    return normalized


@pytest.mark.parametrize(
    "options",
    [
        {"limit": 7, "seed": 12},
        {"profile": "pr"},
        {"profile": "release", "limit": 2, "seed": 7},
        {"profile": "full", "limit": 1, "seed": -4},
        {"profile": "nightly", "dataset": "banking77", "limit": 3},
        {"profile": "nightly", "limit": 4, "seed": 3},
        {"dataset": "massive", "languages": ["fr", "en"], "limit": 3, "seed": 5},
        {"dataset": "massive", "languages": [], "limit": 3, "seed": 5},
    ],
)
def test_rust_registered_runner_matches_python_report(options):
    expected = python_run(**options)
    actual = _rust_run(options)
    assert {key: value for key, value in actual.items() if key != "environment"} == {
        key: value for key, value in expected.items() if key != "environment"
    }


def test_rust_registered_real_run_records_blockers_without_fallback(monkeypatch):
    monkeypatch.setattr(evaluation_base, "datasets_available", lambda: False)
    request = {"profile": "nightly", "source": "real", "limit": 4, "seed": 3}
    expected = python_run(**request)
    actual = _rust_run(request)
    assert {key: value for key, value in actual.items() if key != "environment"} == {
        key: value for key, value in expected.items() if key != "environment"
    }


def test_rust_registered_runner_owns_complete_runtime_grading():
    request = {"profile": "fast", "limit": 5, "seed": 8, "measure_all": True}
    expected = python_run(**request)
    actual = _rust_run(request)

    assert _without_runtime_values(actual) == _without_runtime_values(expected)


def test_rust_registered_runner_owns_reproducibility_environment():
    actual = _rust_run({"dataset": "agentrouter-gold", "limit": 1})["environment"]
    classifier_source = ROOT / "rust" / "agentrouter-classifier" / "src" / "lib.rs"
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
    )

    assert actual["runtime"] == "rust"
    assert actual["git_sha"] == git_sha
    assert actual["git_dirty"] is dirty
    assert actual["classifier_sha256"] == hashlib.sha256(classifier_source.read_bytes()).hexdigest()
    assert actual["rustc"].startswith("rustc ")
    assert actual["agentrouter_version"]
    assert actual["platform"]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"profile": "unknown"}, "unknown profile 'unknown'"),
        ({"dataset": "unknown"}, "unknown dataset 'unknown'"),
        ({"dataset": "agentrouter-gold", "source": "bogus"}, "unknown source 'bogus'"),
        ({"dataset": "massive", "source": "bogus"}, "unknown source 'bogus'"),
        (
            {"dataset": "unknown", "source": "bogus"},
            "unknown dataset 'unknown'",
        ),
        ({"profile": "unknown", "source": "bogus"}, "unknown profile 'unknown'"),
    ],
)
def test_rust_registered_runner_rejects_selection_and_source_errors(payload, message):
    process = _rust_process(payload, check=False)
    assert process.returncode != 0
    assert message in process.stderr
    assert not process.stdout.strip()


@pytest.mark.parametrize("field", ["project_root", "languages", "measure_all"])
def test_rust_registered_runner_rejects_malformed_request_fields(field):
    values = {"project_root": 42, "languages": "en", "measure_all": "yes"}
    request = {"dataset": "massive", field: values[field]}
    process = _rust_process(request, check=False)
    assert process.returncode != 0
    assert not process.stdout.strip()
