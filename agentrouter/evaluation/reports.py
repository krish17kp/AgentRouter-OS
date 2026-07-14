"""Report writers (program §15).

Emits JSON (versioned, stable), Markdown, and CSV (failures + confusion). All
reproducible: no timestamps baked in unless passed by the caller.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPORT_SCHEMA_VERSION = 1


def _confusion_csv(path: Path, matrix: dict[str, dict[str, int]]) -> None:
    labels = sorted(set(matrix) | {p for row in matrix.values() for p in row})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["gold\\pred", *labels])
        for g in labels:
            row = matrix.get(g, {})
            w.writerow([g, *(row.get(p, 0) for p in labels)])


def write_reports(result: dict, out_dir: Path) -> list[Path]:
    """Write result.json, report.md, failures.csv, confusion CSVs, scorecard.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    payload = {"report_schema_version": REPORT_SCHEMA_VERSION, **result}
    (out_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    written.append(out_dir / "result.json")

    scorecard = {
        "grade_over_100": result.get("grade_over_100"),
        "grade_of_measured": result.get("grade_of_measured"),
        "dimensions": result.get("dimensions"),
        "release_gates": result.get("release_gates"),
        "release_ready": result.get("release_ready"),
    }
    (out_dir / "scorecard.json").write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    written.append(out_dir / "scorecard.json")

    (out_dir / "report.md").write_text(render_markdown(result), encoding="utf-8")
    written.append(out_dir / "report.md")

    m = result.get("classification", {})
    failures = m.get("failures", [])
    csv_path = out_dir / "failures.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "prompt", "dimension", "expected", "predicted"])
        for c in failures:
            for fd in c["failed"]:
                w.writerow(
                    [
                        c["id"],
                        c["prompt"],
                        fd["dim"],
                        "|".join(map(str, fd["expected"])),
                        "|".join(map(str, fd["predicted"]))
                        if isinstance(fd["predicted"], list)
                        else fd["predicted"],
                    ]
                )
    written.append(csv_path)

    if "confusion_task_type" in m:
        _confusion_csv(out_dir / "confusion_task_type.csv", m["confusion_task_type"])
        written.append(out_dir / "confusion_task_type.csv")
    if "confusion_risk" in m:
        _confusion_csv(out_dir / "confusion_risk.csv", m["confusion_risk"])
        written.append(out_dir / "confusion_risk.csv")

    return written


def render_markdown(result: dict) -> str:
    m = result.get("classification", {})
    lines = ["# Evaluation report", ""]
    if env := result.get("environment"):
        lines += ["## Environment", ""]
        for k, v in env.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    lines += [
        "## Grade",
        "",
        f"- **Grade /100 (unmeasured = 0):** {result.get('grade_over_100')}",
        f"- **Grade of measured dimensions:** {result.get('grade_of_measured')} "
        f"(measured {result.get('possible_measured_points')}/100 pts)",
        f"- **Release ready:** {'YES' if result.get('release_ready') else 'NO'}",
        f"- **Cases graded:** {result.get('n_cases')}",
        "",
        "## Dimensions",
        "",
        "| dimension | weight | status | score | achieved |",
        "|---|---|---|---|---|",
    ]
    for name, d in (result.get("dimensions") or {}).items():
        score = "-" if d["score"] is None else f"{d['score']:.3f}"
        lines.append(f"| {name} | {d['weight']} | {d['status']} | {score} | {d['achieved']} |")
    lines += ["", "## Release gates", ""]
    for name, ok in (result.get("release_gates") or {}).items():
        lines.append(f"- [{'PASS' if ok else 'FAIL'}] {name}")
    if m:
        lines += [
            "",
            "## Classification highlights",
            "",
            f"- task-type macro F1: {m['task_type']['macro_f1']}",
            f"- high-risk recall: {m.get('high_risk_recall')}",
            f"- tool F1: {m['tools']['f1']}",
            f"- context accuracy: {m['context']['accuracy']}",
            f"- failed cases: {len(m.get('failures', []))}",
        ]
    lines += ["", "## Limitations", ""]
    for name, d in (result.get("dimensions") or {}).items():
        if d["status"] == "pending":
            lines.append(f"- `{name}` dimension not yet measured (evaluator pending).")
    return "\n".join(lines) + "\n"
