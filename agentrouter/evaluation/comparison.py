"""Baseline-vs-current comparison (program §15).

Diffs two result payloads and flags regressions vs improvements per dimension
and per release gate. Regressions are what block a release; improvements are
informational.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

# a dimension score drop beyond this is a regression (not just noise)
REGRESSION_EPSILON = 1e-4


def _dim_scores(result: dict) -> dict[str, float]:
    out = {}
    for name, d in (result.get("dimensions") or {}).items():
        if d.get("score") is not None:
            out[name] = d["score"]
    return out


def compare(baseline: dict, current: dict) -> dict:
    b, c = _dim_scores(baseline), _dim_scores(current)
    regressions, improvements = [], []
    for name in sorted(set(b) & set(c)):
        delta = round(c[name] - b[name], 6)
        row = {"dimension": name, "baseline": b[name], "current": c[name], "delta": delta}
        if delta < -REGRESSION_EPSILON:
            regressions.append(row)
        elif delta > REGRESSION_EPSILON:
            improvements.append(row)

    bg = baseline.get("release_gates") or {}
    cg = current.get("release_gates") or {}
    gate_regressions = [g for g in cg if bg.get(g) and not cg[g]]

    return {
        "regressions": regressions,
        "improvements": improvements,
        "gate_regressions": gate_regressions,
        "grade_delta": round(
            (current.get("grade_over_100") or 0) - (baseline.get("grade_over_100") or 0), 2
        ),
        "has_critical_regression": bool(regressions) or bool(gate_regressions),
    }


def load_result(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_comparison(cmp: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    lines = [
        "# Baseline vs current",
        "",
        f"- grade delta: {cmp['grade_delta']}",
        f"- critical regression: {'YES' if cmp['has_critical_regression'] else 'NO'}",
        f"- gate regressions: {cmp['gate_regressions'] or 'none'}",
        "",
        "## Regressions",
        "",
    ]
    for r in cmp["regressions"]:
        lines.append(f"- {r['dimension']}: {r['baseline']} -> {r['current']} ({r['delta']:+})")
    lines += ["", "## Improvements", ""]
    for r in cmp["improvements"]:
        lines.append(f"- {r['dimension']}: {r['baseline']} -> {r['current']} ({r['delta']:+})")
    (out_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(out_dir / "comparison.md")

    csv_sets = (("regressions.csv", cmp["regressions"]), ("improvements.csv", cmp["improvements"]))
    for fname, rows in csv_sets:
        p = out_dir / fname
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["dimension", "baseline", "current", "delta"])
            for r in rows:
                w.writerow([r["dimension"], r["baseline"], r["current"], r["delta"]])
        written.append(p)
    return written
