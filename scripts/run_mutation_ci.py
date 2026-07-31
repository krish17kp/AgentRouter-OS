"""Run and gate the bounded Linux mutation campaign used by GitHub Actions.

Exit codes are intentionally distinct:

* 0: tool completed and every mutation gate passed;
* 1: tool completed, but score/survivor gates failed;
* 2: environment, timeout, tool, or incomplete-result failure.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

EXPECTED_MUTMUT_VERSION = "3.6.0"
MUTANT_PATTERNS = (
    "agentrouter.safety.*",
    "agentrouter.controls.*",
    "agentrouter.engine.*",
    "agentrouter.hosts.*",
    "agentrouter.server.limits.*",
    "agentrouter.cli.x_execute__mutmut_*",
    "agentrouter.cli.x__execute_via_host__mutmut_*",
)
GROUPS = {
    "safety_policy_execution": {
        "patterns": (
            "agentrouter.safety.*",
            "agentrouter.controls.*",
            "agentrouter.hosts.*",
            "agentrouter.server.limits.*",
            "agentrouter.cli.x_execute__mutmut_*",
            "agentrouter.cli.x__execute_via_host__mutmut_*",
        ),
        "threshold": 0.95,
    },
    "routing_engine": {
        "patterns": ("agentrouter.engine.*",),
        "threshold": 0.85,
    },
}
OVERALL_THRESHOLD = 0.85
EXIT_STATUS = {
    0: "survived",
    1: "killed",
    2: "interrupted",
    3: "killed",
    5: "no_tests",
    24: "timeout",
    33: "no_tests",
    34: "skipped",
    35: "suspicious",
    36: "timeout",
    37: "caught_by_type_check",
    152: "timeout",
    255: "timeout",
    -9: "segfault",
    -11: "segfault",
    -24: "timeout",
    None: "not_checked",
}
KILLED_EQUIVALENT = frozenset({"killed", "timeout", "caught_by_type_check"})
INCOMPLETE = frozenset(
    {"interrupted", "no_tests", "skipped", "suspicious", "segfault", "not_checked", "unknown"}
)


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def load_records(mutants_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for meta_path in sorted(mutants_dir.rglob("*.py.meta")):
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            results = payload["exit_code_by_key"]
        except (OSError, KeyError, json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(f"invalid mutmut metadata {meta_path}: {exc}") from exc
        if not isinstance(results, dict):
            raise RuntimeError(f"invalid exit_code_by_key in {meta_path}")
        for name, exit_code in sorted(results.items()):
            if not _matches(name, MUTANT_PATTERNS):
                continue
            status = EXIT_STATUS.get(exit_code, "unknown")
            records.append(
                {
                    "name": name,
                    "exit_code": exit_code,
                    "status": status,
                    "meta": meta_path.relative_to(mutants_dir).as_posix(),
                }
            )
    return records


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(record["status"] for record in records)
    killed = sum(counts[status] for status in KILLED_EQUIVALENT)
    survived = counts["survived"]
    denominator = killed + survived
    return {
        "score": round(killed / denominator, 4) if denominator else None,
        "killed_equivalent": killed,
        "survived": survived,
        "denominator": denominator,
        "counts": dict(sorted(counts.items())),
        "incomplete": sum(counts[status] for status in INCOMPLETE),
    }


def load_allowlist(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid survivor allowlist {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("mutation survivor allowlist must be a JSON object")
    for mutant, rationale in raw.items():
        if (
            not isinstance(mutant, str)
            or not isinstance(rationale, str)
            or len(rationale.strip()) < 10
        ):
            raise RuntimeError(f"survivor allowlist entry needs a specific rationale: {mutant!r}")
    return raw


def summarize(mutants_dir: Path, allowlist_path: Path) -> dict[str, Any]:
    records = load_records(mutants_dir)
    if not records:
        raise RuntimeError("mutmut produced no selected critical-module records")
    missing_patterns = [
        pattern
        for pattern in MUTANT_PATTERNS
        if not any(fnmatch.fnmatch(r["name"], pattern) for r in records)
    ]
    allowlist = load_allowlist(allowlist_path)
    survivors = [record for record in records if record["status"] == "survived"]
    survivor_names = {record["name"] for record in survivors}
    unreviewed = [record for record in survivors if record["name"] not in allowlist]
    stale_allowlist = sorted(set(allowlist) - survivor_names)

    overall = _score(records)
    groups: dict[str, Any] = {}
    for name, config in GROUPS.items():
        selected = [record for record in records if _matches(record["name"], config["patterns"])]
        group = _score(selected)
        group["threshold"] = config["threshold"]
        group["passed"] = (
            bool(selected)
            and group["score"] is not None
            and group["score"] >= config["threshold"]
            and group["incomplete"] == 0
        )
        groups[name] = group

    gates = {
        f"overall_score>={OVERALL_THRESHOLD:.2f}": (
            overall["score"] is not None and overall["score"] >= OVERALL_THRESHOLD
        ),
        "selected_results_complete": overall["incomplete"] == 0 and not missing_patterns,
        "all_survivors_reviewed_non_bypass": not unreviewed,
        **{
            f"{name}_score>={data['threshold']:.2f}": data["passed"]
            for name, data in groups.items()
        },
    }
    return {
        "schema_version": 1,
        "tool": {"name": "mutmut", "version": EXPECTED_MUTMUT_VERSION},
        "selection": list(MUTANT_PATTERNS),
        "score_definition": (
            "(killed + timeout + caught_by_type_check) / "
            "(killed + timeout + caught_by_type_check + survived)"
        ),
        "overall": {**overall, "threshold": OVERALL_THRESHOLD},
        "groups": groups,
        "missing_patterns": missing_patterns,
        "survivors": [
            {
                **record,
                "review": "allowlisted_non_bypass" if record["name"] in allowlist else "unreviewed",
                "rationale": allowlist.get(record["name"]),
            }
            for record in survivors
        ],
        "unreviewed_survivors": [record["name"] for record in unreviewed],
        "stale_allowlist": stale_allowlist,
        "gates": gates,
        "passed": all(gates.values()),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Critical-module mutation report",
        "",
        f"- Outcome: **{'PASS' if report['passed'] else 'FAIL'}**",
        f"- Overall score: `{report['overall']['score']}` "
        f"(target `{report['overall']['threshold']}`)",
        f"- Selected denominator: `{report['overall']['denominator']}` mutants",
        f"- Unreviewed survivors: `{len(report['unreviewed_survivors'])}`",
        "",
        "## Group scores",
        "",
        "| group | score | target | complete | pass |",
        "|---|---:|---:|---:|---|",
    ]
    for name, group in report["groups"].items():
        lines.append(
            f"| {name} | {group['score']} | {group['threshold']} | "
            f"{group['incomplete'] == 0} | {'PASS' if group['passed'] else 'FAIL'} |"
        )
    lines += ["", "## Gates", ""]
    for name, passed in report["gates"].items():
        lines.append(f"- [{'PASS' if passed else 'FAIL'}] {name}")
    lines += ["", "## Survivors", ""]
    if not report["survivors"]:
        lines.append("No survivors.")
    for survivor in report["survivors"]:
        lines.append(
            f"- `{survivor['name']}` - {survivor['review']}"
            + (f": {survivor['rationale']}" if survivor["rationale"] else "")
        )
    if report["missing_patterns"]:
        lines += ["", "## Missing selections", ""]
        lines.extend(f"- `{pattern}`" for pattern in report["missing_patterns"])
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    survivor_lines = [
        f"{item['review']}\t{item['name']}\t{item.get('rationale') or ''}"
        for item in report["survivors"]
    ]
    (out_dir / "survivors.txt").write_text(
        "\n".join(survivor_lines) + ("\n" if survivor_lines else ""), encoding="utf-8"
    )


def write_tool_failure(out_dir: Path, status: str, detail: str, command: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "tool": {"name": "mutmut", "expected_version": EXPECTED_MUTMUT_VERSION},
        "status": status,
        "detail": detail,
        "command": command,
        "score": None,
    }
    (out_dir / "tool-status.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (out_dir / "report.md").write_text(
        "# Critical-module mutation report\n\n"
        f"- Outcome: **TOOL FAILURE**\n- Status: `{status}`\n- Detail: {detail}\n",
        encoding="utf-8",
    )


def _tail(path: Path, lines: int = 80) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(content[-lines:])


def run_campaign(repo: Path, out_dir: Path, timeout_seconds: int, max_children: int) -> int:
    command = ["mutmut", "run", "--max-children", str(max_children), *MUTANT_PATTERNS]
    if platform.system() != "Linux":
        write_tool_failure(
            out_dir, "environment_failure", "mutmut 3 campaign requires Linux", command
        )
        return 2
    try:
        installed = version("mutmut")
    except PackageNotFoundError:
        write_tool_failure(out_dir, "environment_failure", "mutmut is not installed", command)
        return 2
    if installed != EXPECTED_MUTMUT_VERSION:
        write_tool_failure(
            out_dir,
            "environment_failure",
            f"expected mutmut {EXPECTED_MUTMUT_VERSION}, found {installed}",
            command,
        )
        return 2
    mutants_dir = repo / "mutants"
    if mutants_dir.exists():
        write_tool_failure(
            out_dir,
            "environment_failure",
            "generated mutants/ already exists; a fresh checkout is required for reproducible CI",
            command,
        )
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "mutmut.log"
    status_path = out_dir / "tool-status.json"
    status_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tool": {"name": "mutmut", "version": installed},
                "status": "running",
                "command": command,
                "timeout_seconds": timeout_seconds,
                "max_children": max_children,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(  # nosec B603 - fixed tool + fixed audited arguments
                command,
                cwd=repo,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
                env={**os.environ, "PYTHONHASHSEED": "0"},
            )
    except subprocess.TimeoutExpired:
        detail = f"mutmut exceeded the explicit {timeout_seconds}-second command timeout"
        write_tool_failure(out_dir, "timeout", detail, command)
        print(detail, file=sys.stderr)
        return 2
    except OSError as exc:
        write_tool_failure(out_dir, "tool_failure", str(exc), command)
        print(f"mutation tool failed to start: {exc}", file=sys.stderr)
        return 2
    if completed.returncode != 0:
        detail = f"mutmut exited {completed.returncode}; see mutmut.log"
        write_tool_failure(out_dir, "tool_failure", detail, command)
        print(_tail(log_path), file=sys.stderr)
        print(detail, file=sys.stderr)
        return 2

    try:
        report = summarize(mutants_dir, repo / "mutation-survivor-allowlist.json")
    except RuntimeError as exc:
        write_tool_failure(out_dir, "incomplete_results", str(exc), command)
        print(f"mutation results incomplete: {exc}", file=sys.stderr)
        return 2
    write_report(report, out_dir)
    status_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tool": {"name": "mutmut", "version": installed},
                "status": "completed",
                "command": command,
                "timeout_seconds": timeout_seconds,
                "score_gates_passed": report["passed"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(render_markdown(report))
    return 0 if report["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=2100)
    parser.add_argument("--max-children", type=int, default=4)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    out_dir = repo / "artifacts" / "mutation"
    if args.timeout_seconds < 60 or args.max_children < 1:
        parser.error("timeout must be >=60 seconds and max-children must be >=1")
    if args.report_only:
        try:
            report = summarize(repo / "mutants", repo / "mutation-survivor-allowlist.json")
        except RuntimeError as exc:
            write_tool_failure(out_dir, "incomplete_results", str(exc), [])
            return 2
        write_report(report, out_dir)
        print(render_markdown(report))
        return 0 if report["passed"] else 1
    return run_campaign(repo, out_dir, args.timeout_seconds, args.max_children)


if __name__ == "__main__":
    raise SystemExit(main())
