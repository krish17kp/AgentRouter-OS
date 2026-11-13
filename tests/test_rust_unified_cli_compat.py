"""Smoke and dispatch checks for the unified Rust `agentrouter` executable."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

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


def test_unknown_or_unported_command_fails_with_usage(unified_binary):
    result = _run(unified_binary, "plugin")
    assert result.returncode == 2
    assert "not-yet-ported" in result.stderr
    assert "dataset" in result.stderr
