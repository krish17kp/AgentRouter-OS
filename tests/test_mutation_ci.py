"""Contract tests for the Linux mutation result parser and gates."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_mutation_ci.py"
SPEC = importlib.util.spec_from_file_location("run_mutation_ci", SCRIPT)
assert SPEC and SPEC.loader
mutation_ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mutation_ci)


def _write_meta(mutants: Path, relative: str, results: dict[str, int | None]) -> None:
    path = mutants / f"{relative}.meta"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"exit_code_by_key": results}), encoding="utf-8")


def _complete_records(mutants: Path, *, survivor: str | None = None) -> None:
    records = {
        "agentrouter/safety.py": {"agentrouter.safety.x_gates_for__mutmut_1": 1},
        "agentrouter/controls.py": {"agentrouter.controls.x_apply_controls__mutmut_1": 1},
        "agentrouter/engine.py": {"agentrouter.engine.x_route__mutmut_1": 1},
        "agentrouter/hosts.py": {"agentrouter.hosts.x_command_preview__mutmut_1": 1},
        "agentrouter/server/limits.py": {"agentrouter.server.limits.x_client_key__mutmut_1": 1},
        "agentrouter/cli.py": {
            "agentrouter.cli.x__execute__mutmut_1": 1,
            "agentrouter.cli.x__execute_via_host__mutmut_1": 1,
        },
    }
    if survivor:
        for result in records.values():
            if survivor in result:
                result[survivor] = 0
    for relative, result in records.items():
        _write_meta(mutants, relative, result)


def test_complete_killed_campaign_passes(tmp_path):
    mutants = tmp_path / "mutants"
    _complete_records(mutants)
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text("{}", encoding="utf-8")

    report = mutation_ci.summarize(mutants, allowlist)

    assert report["passed"] is True
    assert report["overall"]["score"] == 1.0
    assert report["missing_patterns"] == []


def test_unreviewed_survivor_fails_even_when_numeric_score_passes(tmp_path):
    survivor = "agentrouter.safety.x_gates_for__mutmut_1"
    mutants = tmp_path / "mutants"
    _complete_records(mutants, survivor=survivor)
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text("{}", encoding="utf-8")

    report = mutation_ci.summarize(mutants, allowlist)

    assert report["gates"]["all_survivors_reviewed_non_bypass"] is False
    assert report["passed"] is False
    assert report["survivors"][0]["review"] == "unreviewed"


def test_reviewed_non_bypass_survivor_is_named_and_scored(tmp_path):
    survivor = "agentrouter.engine.x_route__mutmut_1"
    mutants = tmp_path / "mutants"
    _complete_records(mutants, survivor=survivor)
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps({survivor: "Equivalent ordering only; no routing or policy behavior changes."}),
        encoding="utf-8",
    )

    report = mutation_ci.summarize(mutants, allowlist)

    assert report["unreviewed_survivors"] == []
    assert report["survivors"][0]["name"] == survivor
    assert report["survivors"][0]["rationale"]
    assert report["overall"]["score"] < 1.0


@pytest.mark.parametrize("exit_code", [None, 5, 35, -11])
def test_incomplete_or_crashed_mutant_never_passes(tmp_path, exit_code):
    mutants = tmp_path / "mutants"
    _complete_records(mutants)
    meta = mutants / "agentrouter/safety.py.meta"
    payload = json.loads(meta.read_text(encoding="utf-8"))
    payload["exit_code_by_key"]["agentrouter.safety.x_gates_for__mutmut_1"] = exit_code
    meta.write_text(json.dumps(payload), encoding="utf-8")

    report = mutation_ci.summarize(mutants, tmp_path / "missing-allowlist.json")

    assert report["overall"]["incomplete"] == 1
    assert report["gates"]["selected_results_complete"] is False
    assert report["passed"] is False


def test_missing_selected_function_is_an_incomplete_result(tmp_path):
    mutants = tmp_path / "mutants"
    _complete_records(mutants)
    (mutants / "agentrouter/cli.py.meta").unlink()

    report = mutation_ci.summarize(mutants, tmp_path / "missing-allowlist.json")

    assert "agentrouter.cli.x__execute__mutmut_*" in report["missing_patterns"]
    assert report["passed"] is False
