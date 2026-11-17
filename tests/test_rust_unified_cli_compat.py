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

from agentrouter import refresh
from agentrouter.annotation import candidates as candidate_mod
from agentrouter.annotation import store
from agentrouter.controls import PREFERENCE_WEIGHTS

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
    assert "contract" in help_result.stdout
    assert "--live URL" in help_result.stdout
    assert "export" in help_result.stdout

    python_help = subprocess.run(
        [sys.executable, "-m", "agentrouter", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert python_help.returncode == 0, python_help.stderr
    for command in ("route", "registry", "providers", "doctor"):
        assert command in python_help.stdout
        assert command in help_result.stdout

    version = _run(unified_binary, "--version")
    assert version.returncode == 0
    assert version.stdout.strip() == "agentrouter 0.5.0rc1"


def test_unified_route_help_is_successful_and_lists_route_options(unified_binary):
    result = _run(unified_binary, "route", "--help")
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("Usage: agentrouter route")
    assert "--context-tokens" in result.stdout


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (("init", "--help"), "Usage: agentrouter init"),
        (("explain", "--help"), "Usage: agentrouter explain"),
        (("feedback", "--help"), "Usage: agentrouter feedback"),
        (("stats", "--help"), "Usage: agentrouter stats"),
        (("prompt", "--help"), "Usage: agentrouter prompt"),
        (("doctor", "--help"), "Usage: agentrouter doctor"),
        (("dashboard", "--help"), "Usage: agentrouter dashboard"),
    ],
)
def test_unified_leaf_command_help_is_successful(unified_binary, arguments, expected):
    result = _run(unified_binary, *arguments)
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith(expected)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (("models", "list", "--help"), "Usage: agentrouter models list"),
        (("hosts", "doctor", "--help"), "Usage: agentrouter hosts doctor"),
        (("providers", "status", "--help"), "Usage: agentrouter providers status"),
        (("providers", "refresh", "--help"), "Usage: agentrouter providers refresh"),
        (("providers", "rollback", "--help"), "Usage: agentrouter providers rollback"),
        (("providers", "restore", "--help"), "Usage: agentrouter providers restore"),
        (("registry", "list", "--help"), "Usage: agentrouter registry list"),
    ],
)
def test_unified_core_group_help_is_successful(unified_binary, arguments, expected):
    result = _run(unified_binary, *arguments)
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith(expected)


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


def test_explain_supports_python_text_and_json_surfaces(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    routed = _run(
        unified_binary,
        "route",
        "Review this Python repository for security issues.",
        "--save",
        "--json",
        home=home,
    )
    assert routed.returncode == 0, routed.stderr
    decision_id = json.loads(routed.stdout)["decision_id"]

    json_result = _run(unified_binary, "explain", decision_id, "--json", home=home)
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["task"] == "Review this Python repository for security issues."
    assert payload["classification"]["risk"] == "medium"

    text_result = _run(unified_binary, "explain", decision_id, home=home)
    assert text_result.returncode == 0, text_result.stderr
    assert text_result.stdout.startswith('Task: "Review this Python repository for security issues."')
    assert "Eligibility:" in text_result.stdout
    assert "Scores" in text_result.stdout
    assert "Gate: approval=" in text_result.stdout


def test_unified_prompt_can_write_an_execution_file(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    routed = _run(
        unified_binary,
        "route",
        "Summarize this report",
        "--save",
        "--json",
        home=home,
    )
    assert routed.returncode == 0, routed.stderr
    decision_id = json.loads(routed.stdout)["decision_id"]
    output = tmp_path / "execution-prompt.md"
    generated = _run(
        unified_binary,
        "prompt",
        "generate",
        "--from",
        decision_id,
        "--out",
        output,
        home=home,
    )
    assert generated.returncode == 0, generated.stderr
    assert output.read_text(encoding="utf-8").startswith("# Execution Prompt\n")
    assert generated.stdout.endswith(f" -> {output}\n")


def test_unified_stored_prompt_matches_python_newline_contract(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    routed = _run(
        unified_binary,
        "route",
        "Summarize this report",
        "--save",
        "--json",
        home=home,
    )
    assert routed.returncode == 0, routed.stderr
    decision_id = json.loads(routed.stdout)["decision_id"]
    rust = _run(unified_binary, "prompt", "generate", "--from", decision_id, home=home)
    python_env = os.environ.copy()
    python_env["AGENTROUTER_HOME"] = str(home)
    python = subprocess.run(
        [sys.executable, "-m", "agentrouter", "prompt", "generate", "--from", decision_id],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=python_env,
        timeout=60,
        check=False,
    )
    assert rust.returncode == python.returncode == 0
    assert rust.stdout == python.stdout
    assert rust.stderr == python.stderr


def test_unified_prompt_accepts_task_text_like_python(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    task = "Summarize this report"
    rust = _run(unified_binary, "prompt", "generate", task, home=home)
    python_env = os.environ.copy()
    python_env["AGENTROUTER_HOME"] = str(home)
    python = subprocess.run(
        [sys.executable, "-m", "agentrouter", "prompt", "generate", task],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=python_env,
        timeout=60,
        check=False,
    )
    assert rust.returncode == python.returncode == 0
    assert rust.stdout == python.stdout
    assert rust.stderr == python.stderr


def test_unified_prompt_task_uses_python_weight_config_without_policy_cap(
    tmp_path, unified_binary
):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    (home / "config.yaml").write_text(
        "weights:\n  w_cap: 0.70\n  w_cost: 0.10\n  w_lat: 0.10\n  w_ctx: 0.10\n"
        "policy:\n  max_pricing_tier: low\n",
        encoding="utf-8",
    )
    task = "summarize this report"
    rust = _run(unified_binary, "prompt", "generate", task, home=home)
    python_env = os.environ.copy()
    python_env["AGENTROUTER_HOME"] = str(home)
    python = subprocess.run(
        [sys.executable, "-m", "agentrouter", "prompt", "generate", task],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=python_env,
        timeout=60,
        check=False,
    )
    assert rust.returncode == python.returncode == 0
    assert rust.stdout == python.stdout


def test_read_only_execution_plan_never_enables_execution(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    initialized = _run(unified_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    saved = _run(
        unified_binary,
        "route",
        "summarize a support ticket",
        "--save",
        "--json",
        home=home,
    )
    assert saved.returncode == 0, saved.stderr
    decision_id = json.loads(saved.stdout)["decision_id"]

    planned = _run(unified_binary, "plan", decision_id, "--json", home=home)
    assert planned.returncode == 0, planned.stderr
    payload = json.loads(planned.stdout)
    assert payload["status"] == "planned"
    assert payload["execution_enabled"] is False
    assert payload["command_preview"].endswith("<prompt redacted>")

    explicitly_requested = _run(
        unified_binary,
        "plan",
        decision_id,
        "--json",
        "--allow-remote",
        "--approve",
        home=home,
    )
    assert explicitly_requested.returncode == 0, explicitly_requested.stderr
    assert json.loads(explicitly_requested.stdout)["execution_enabled"] is False


def test_workflow_plan_is_read_only_and_rejects_duplicate_dependencies(unified_binary):
    workflow = {
        "steps": [
            {"id": "prepare", "estimated_cost": 2},
            {
                "id": "write",
                "depends_on": ["prepare"],
                "side_effect_key": "file:report",
                "idempotency_key": "report-v1",
                "estimated_cost": 3,
            },
        ]
    }
    planned = subprocess.run(
        [str(unified_binary), "workflow", "plan", "--json"],
        cwd=ROOT,
        input=json.dumps(workflow),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert planned.returncode == 0, planned.stderr
    payload = json.loads(planned.stdout)
    assert payload["ordered_steps"] == ["prepare", "write"]
    assert payload["estimated_cost"] == 5
    assert payload["execution_enabled"] is False

    tool_workflow = {"steps": [{"id": "inspect", "required_tools": ["read"], "estimated_cost": 1}]}
    denied_tool = subprocess.run(
        [str(unified_binary), "workflow", "plan", "--json"],
        cwd=ROOT,
        input=json.dumps(tool_workflow),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert denied_tool.returncode == 2
    allowed_tool = subprocess.run(
        [str(unified_binary), "workflow", "plan", "--json", "--allow-tool", "read"],
        cwd=ROOT,
        input=json.dumps(tool_workflow),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert allowed_tool.returncode == 0, allowed_tool.stderr
    assert json.loads(allowed_tool.stdout)["execution_enabled"] is False

    malformed = {
        "steps": [
            {"id": "root", "estimated_cost": 1},
            {"id": "child", "depends_on": ["root", "root"], "estimated_cost": 1},
        ]
    }
    rejected = subprocess.run(
        [str(unified_binary), "workflow", "plan", "--json"],
        cwd=ROOT,
        input=json.dumps(malformed),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert rejected.returncode == 2
    assert "dependency" in rejected.stderr and "more than once" in rejected.stderr


def test_contract_cli_checks_baseline_and_reports_surface_changes(tmp_path, unified_binary):
    checked = _run(unified_binary, "contract", "check", "--json")
    assert checked.returncode == 0, checked.stderr
    payload = json.loads(checked.stdout)
    assert payload["status"] == "ok"
    assert payload["references_valid"] is True
    assert payload["live_schema_check"] is False

    baseline = json.loads((ROOT / "contracts/http/v1/openapi.json").read_text(encoding="utf-8"))
    additive = dict(baseline)
    additive["paths"] = dict(baseline["paths"])
    additive["paths"]["/__compat_probe__"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    additive_path = tmp_path / "additive.json"
    additive_path.write_text(json.dumps(additive), encoding="utf-8")
    additive_result = _run(unified_binary, "contract", "diff", additive_path, "--json")
    assert additive_result.returncode == 0, additive_result.stderr
    additive_report = json.loads(additive_result.stdout)
    assert additive_report["compatible"] is True
    assert additive_report["counts"]["additive"] == 1

    breaking = dict(baseline)
    breaking["paths"] = dict(baseline["paths"])
    breaking["paths"].pop(next(iter(breaking["paths"])))
    breaking_path = tmp_path / "breaking.json"
    breaking_path.write_text(json.dumps(breaking), encoding="utf-8")
    breaking_result = _run(unified_binary, "contract", "diff", breaking_path, "--json")
    assert breaking_result.returncode == 1
    assert json.loads(breaking_result.stdout)["compatible"] is False

    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text(json.dumps({"openapi": "3.1.0", "paths": {"/x": {"$ref": "#/missing"}}}), encoding="utf-8")
    malformed_result = _run(unified_binary, "contract", "diff", malformed_path, "--json")
    assert malformed_result.returncode == 2
    assert "unusable $ref" in malformed_result.stderr


def test_contract_export_requires_and_records_owner_acceptance(tmp_path, unified_binary):
    contract_dir = tmp_path / "contracts" / "http" / "v1"
    contract_dir.mkdir(parents=True)
    baseline_path = ROOT / "contracts" / "http" / "v1" / "openapi.json"
    manifest_path = ROOT / "contracts" / "http" / "v1" / "manifest.json"
    shutil.copy2(baseline_path, contract_dir / "openapi.json")
    shutil.copy2(manifest_path, contract_dir / "manifest.json")

    candidate = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate["paths"] = dict(candidate["paths"])
    removed_path = next(iter(candidate["paths"]))
    candidate["paths"].pop(removed_path)
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    refused = subprocess.run(
        [
            str(unified_binary),
            "contract",
            "export",
            "--source",
            str(candidate_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert refused.returncode == 2
    assert "breaking change" in refused.stderr

    accepted = subprocess.run(
        [
            str(unified_binary),
            "contract",
            "export",
            "--source",
            str(candidate_path),
            "--accept-breaking",
            "--reason",
            "owner-approved compatibility break",
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert accepted.returncode == 0, accepted.stderr
    payload = json.loads(accepted.stdout)
    assert payload["accepted_breaking_changes"] == 1
    manifest = json.loads((contract_dir / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["accepted_breaking_changes"][-1]
    assert entry["reason"] == "owner-approved compatibility break"
    assert any(change["location"] == removed_path for change in entry["changes"])


def test_setup_runs_onboarding_and_persists_selected_preference(
    tmp_path, unified_binary, monkeypatch
):
    home = tmp_path / "agentrouter-home"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-setup-secret-must-not-be-printed")
    setup = _run(
        unified_binary,
        "setup",
        "--preference",
        "cheap",
        "--sample",
        "Summarize this PDF and list action items",
        home=home,
    )
    assert setup.returncode == 0, setup.stderr
    config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    assert config["weights"] == PREFERENCE_WEIGHTS["cheap"]
    assert "1. Home directory" in setup.stdout
    assert "2. Execution hosts" in setup.stdout
    assert "3. Preference: cheap" in setup.stdout
    assert '4. Sample route: "Summarize this PDF and list action items"' in setup.stdout
    assert "5. Install a host integration:" in setup.stdout
    assert "sk-setup-secret-must-not-be-printed" not in setup.stdout + setup.stderr

    config["custom_setting"] = "preserve-me"
    (home / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    repeated = _run(unified_binary, "setup", "--preference", "quality", home=home)
    assert repeated.returncode == 0, repeated.stderr
    assert "exists, skipped" in repeated.stdout
    config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    assert config["weights"] == PREFERENCE_WEIGHTS["quality"]
    assert config["custom_setting"] == "preserve-me"


def test_setup_rejects_unknown_preference_without_initializing_home(tmp_path, unified_binary):
    home = tmp_path / "agentrouter-home"
    setup = _run(unified_binary, "setup", "--preference", "unknown", home=home)
    assert setup.returncode == 2
    assert "Unknown --preference 'unknown'" in setup.stderr
    assert not home.exists()


def test_evaluate_alias_matches_rust_legacy_gold_command(unified_binary):
    legacy_binary = unified_binary.with_name(
        "agentrouter-evaluate" + (".exe" if os.name == "nt" else "")
    )
    arguments = ["--json", "--no-artifacts"]
    direct = subprocess.run(
        [str(legacy_binary), "legacy-gold", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    alias = _run(unified_binary, "evaluate", *arguments)
    assert alias.returncode == direct.returncode == 0
    assert json.loads(alias.stdout) == json.loads(direct.stdout)


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


@pytest.fixture(scope="session")
def refresh_fixture_binary():
    built = subprocess.run(
        [
            "cargo",
            "build",
            "-p",
            "agentrouter-cli",
            "--features",
            "test-fixtures",
            "--bin",
            "agentrouter",
            "--locked",
        ],
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


def test_provider_refresh_fixture_process_matches_python_and_never_writes_on_dry_run_or_error(
    tmp_path, refresh_fixture_binary
):
    home = tmp_path / "agentrouter-home"
    initialized = _run(refresh_fixture_binary, "init", home=home)
    assert initialized.returncode == 0, initialized.stderr
    registry = home / "registry"
    manual = (registry / "models.yaml").read_bytes()
    previous = registry / "models.openrouter.generated.yaml"
    previous.write_text(
        "models:\n  - model_id: retired/model\n    context_window: 1\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "openrouter.json"
    payload = {
        "data": [
            {
                "id": "vendor/frontier-x",
                "context_length": 200000,
                "pricing": {"prompt": "0.00002", "completion": "0.0001"},
                "supported_parameters": ["tools"],
                "architecture": {"input_modalities": ["text"]},
            },
            {
                "id": "vendor/cheap-y",
                "context_length": 32000,
                "pricing": {"prompt": "0"},
            },
        ]
    }
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    env = os.environ.copy()
    env["AGENTROUTER_HOME"] = str(home)
    env["AGENTROUTER_TEST_REFRESH_PAYLOAD"] = str(fixture)

    dry_run = subprocess.run(
        [str(refresh_fixture_binary), "providers", "refresh", "openrouter", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert "candidate deprecation" in dry_run.stdout
    assert "Dry run - nothing written." in dry_run.stdout
    assert previous.read_text(encoding="utf-8").startswith("models:")
    assert not (registry / "models.openrouter.generated.yaml.tmp").exists()

    applied = subprocess.run(
        [str(refresh_fixture_binary), "providers", "refresh", "openrouter", "--limit", "2"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )
    assert applied.returncode == 0, applied.stderr
    assert (registry / "models.yaml").read_bytes() == manual
    generated = yaml.safe_load(previous.read_text(encoding="utf-8"))
    assert generated["provenance"]["provider"] == "openrouter"
    assert generated["provenance"]["source_url"] == "https://openrouter.ai/api/v1/models"
    assert generated["provenance"]["count"] == 2
    for model in generated["models"]:
        if hasattr(model.get("last_updated"), "isoformat"):
            model["last_updated"] = model["last_updated"].isoformat()
    expected = [
        refresh.map_openrouter_model(row).model_dump(mode="json", exclude_none=True)
        for row in payload["data"]
    ]
    assert generated["models"] == expected

    before_failure = previous.read_bytes()
    fixture.write_text("{not-json", encoding="utf-8")
    failed = subprocess.run(
        [str(refresh_fixture_binary), "providers", "refresh", "openrouter"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )
    assert failed.returncode == 1
    assert "registry was NOT modified" in failed.stderr
    assert previous.read_bytes() == before_failure

    openai_fixture = tmp_path / "openai.json"
    openai_fixture.write_text(
        json.dumps({"data": [{"id": "gpt-4.1-mini-2026-01-01"}]}), encoding="utf-8"
    )
    env["AGENTROUTER_TEST_REFRESH_PAYLOAD"] = str(openai_fixture)
    env["OPENAI_API_KEY"] = "sk-fixture-only"
    openai = subprocess.run(
        [str(refresh_fixture_binary), "providers", "refresh", "openai"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )
    assert openai.returncode == 0, openai.stderr
    assert "sk-fixture-only" not in openai.stdout + openai.stderr
    openai_catalog = yaml.safe_load(
        (registry / "models.openai.generated.yaml").read_text(encoding="utf-8")
    )
    assert openai_catalog["provenance"]["source_url"] == "https://api.openai.com/v1/models"
    assert openai_catalog["models"][0]["model_id"] == "gpt-4.1-mini-2026-01-01"
    openai_generated = registry / "models.openai.generated.yaml"
    openai_before_missing_key = openai_generated.read_bytes()

    env.pop("OPENAI_API_KEY")
    missing_key = subprocess.run(
        [str(refresh_fixture_binary), "providers", "refresh", "openai"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )
    assert missing_key.returncode == 1
    assert "OPENAI_API_KEY" in missing_key.stdout + missing_key.stderr
    assert "registry was NOT modified" in missing_key.stderr
    assert "sk-fixture-only" not in missing_key.stdout + missing_key.stderr
    assert openai_generated.read_bytes() == openai_before_missing_key


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
        '{"jsonrpc":"2.0","id":3,"method":"server/discover",'
        '"params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",'
        '"io.modelcontextprotocol/clientInfo":{"name":"test","version":"1"},'
        '"io.modelcontextprotocol/clientCapabilities":{}}}}\n'
        '{"jsonrpc":"2.0","id":4,"method":"tools/list",'
        '"params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",'
        '"io.modelcontextprotocol/clientCapabilities":{}}}}\n'
        '{"jsonrpc":"2.0","id":5,"method":"ping",'
        '"params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",'
        '"io.modelcontextprotocol/clientCapabilities":{}}}}\n'
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
    modern_discovery = responses[2]["result"]
    assert modern_discovery["supportedVersions"] == ["2026-07-28"]
    assert modern_discovery["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "agentrouter"
    assert modern_discovery["cacheScope"] == "private"
    modern_tools = responses[3]["result"]
    assert [tool["name"] for tool in modern_tools["tools"]] == [
        "route",
        "classify",
        "explain",
        "list_models",
        "list_hosts",
    ]
    assert modern_tools["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "agentrouter"
    assert responses[4]["error"]["code"] == -32601


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


def test_unified_execute_missing_command_is_runtime_error(tmp_path, unified_binary):
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
    provider["supports_execution"] = True
    provider["exec_command"] = ["agentrouter-command-that-does-not-exist", "{prompt}"]
    provider_file.write_text(yaml.safe_dump(provider_data), encoding="utf-8")

    failed = _run(unified_binary, "execute", payload["decision_id"], "--yes", home=home)
    assert failed.returncode == 1
    assert "Execution failed: command not found" in failed.stderr


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
    result = _run(unified_binary, "unknown-command")
    assert result.returncode == 2
    assert "not-yet-ported" in result.stderr
    assert "dataset" in result.stderr
