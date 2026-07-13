"""Graded evaluation of the classifier against a gold benchmark.

Loads benchmarks/classifier_gold_v1.yaml, runs the rule-based classifier over
every prompt (pure inference — no overrides), and grades each of 7 dimensions.
Dimensions accept a *set* of labels so genuinely ambiguous prompts are not
force-fit to one answer: a prediction is correct when it lands in the set.

approval is a deterministic function of risk in the classifier
(low->auto, medium->notify, high->human-approval-required), so its gold set is
derived from the risk set and its accuracy necessarily tracks risk accuracy.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import yaml

from .classifier import classify
from .engine import route as engine_route
from .schema import (
    ApprovalLevel,
    Classification,
    ContextBand,
    Level,
    ModelEntry,
    OutputType,
    PricingTier,
    TaskType,
)

TASK_TYPES = ["coding", "reasoning", "writing", "analysis", "summarization", "general"]
LEVELS = ["low", "medium", "high"]
RISK_TO_APPROVAL = {"low": "auto", "medium": "notify", "high": "human-approval-required"}

# per-dimension grade weights (sum = 30); overall grade rescales to 0..100
GRADE_WEIGHTS = {
    "task_type": 10,
    "risk": 7,
    "complexity": 4,
    "tools": 4,
    "output": 2,
    "context": 2,
    "approval": 1,
}


class GoldError(Exception):
    """Raised on a malformed gold benchmark file."""


def load_gold(path: Path) -> list[dict]:
    if not path.exists():
        raise GoldError(f"gold benchmark not found: {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("cases"), list):
        raise GoldError(f"{path}: expected a mapping with a 'cases' list")
    cases = doc["cases"]
    ids = [c.get("id") for c in cases]
    if len(set(ids)) != len(ids):
        raise GoldError(f"{path}: duplicate case ids present")
    return cases


def _as_set(value) -> list[str]:
    """Accept a single label or a list; return a list of acceptable labels."""
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _predict(prompt: str, classify_fn) -> dict:
    c = classify_fn(prompt)
    return {
        "task_type": c.task_type.value,
        "complexity": c.complexity.value,
        "risk": c.risk.value,
        "output": c.output_type.value,
        "context": c.context_band.value,
        "approval": c.approval_level.value,
        "tools": set(c.tool_needs),
    }


def _score_single(pairs: list[tuple[list[str], str]]) -> dict:
    """Accuracy + macro-F1 + per-class recall for a single-label dimension.

    pairs: (acceptable_labels, predicted). Convention when a prediction misses:
    the first acceptable label is the canonical gold (FN there), the prediction
    is a false positive for its own class. When it hits, it is a TP for the
    predicted class. Macro-F1 averages over classes with any support.
    """
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    correct = 0
    for acceptable, pred in pairs:
        if pred in acceptable:
            correct += 1
            tp[pred] += 1
        else:
            fn[acceptable[0]] += 1
            fp[pred] += 1
    classes = set(tp) | set(fp) | set(fn)
    f1s: list[float] = []
    recall: dict[str, float] = {}
    for c in sorted(classes):
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) else 0.0
        r = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) else 0.0
        f1s.append(2 * p * r / (p + r) if (p + r) else 0.0)
        if tp[c] + fn[c]:
            recall[c] = round(r, 4)
    return {
        "accuracy": round(correct / len(pairs), 4) if pairs else 0.0,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
        "per_class_recall": recall,
        "n": len(pairs),
    }


def _score_tools(pairs: list[tuple[set[str], set[str]]]) -> dict:
    """Micro precision/recall/F1 over predicted vs expected tool sets."""
    tp = fp = fn = 0
    exact = 0
    for gold, pred in pairs:
        tp += len(pred & gold)
        fp += len(pred - gold)
        fn += len(gold - pred)
        exact += pred == gold
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact_set_accuracy": round(exact / len(pairs), 4) if pairs else 0.0,
        "n": len(pairs),
    }


def grade_cases(cases: list[dict], classify_fn=classify) -> dict:
    """Grade a list of gold cases. Returns the full metrics report."""
    single = {d: [] for d in ("task_type", "complexity", "risk", "output", "context", "approval")}
    tools_pairs: list[tuple[set[str], set[str]]] = []
    per_case: list[dict] = []

    for case in cases:
        prompt = case["prompt"]
        pred = _predict(prompt, classify_fn)
        gold = {
            "task_type": _as_set(case.get("task_type")),
            "complexity": _as_set(case.get("complexity")),
            "risk": _as_set(case.get("risk")),
            "output": _as_set(case.get("output_type")),
            "context": _as_set(case.get("context_band")),
        }
        gold["approval"] = (
            sorted({RISK_TO_APPROVAL[r] for r in gold["risk"]}) if gold["risk"] else []
        )

        failed_dims: list[dict] = []
        for dim in single:
            if not gold[dim]:  # dimension not graded for this case
                continue
            single[dim].append((gold[dim], pred[dim]))
            if pred[dim] not in gold[dim]:
                failed_dims.append({"dim": dim, "expected": gold[dim], "predicted": pred[dim]})

        if "tools" in case:
            gold_tools = set(case["tools"] or [])
            tools_pairs.append((gold_tools, pred["tools"]))
            if pred["tools"] != gold_tools:
                failed_dims.append(
                    {
                        "dim": "tools",
                        "expected": sorted(gold_tools),
                        "predicted": sorted(pred["tools"]),
                    }
                )

        per_case.append(
            {
                "id": case.get("id"),
                "prompt": prompt,
                "predicted": {**pred, "tools": sorted(pred["tools"])},
                "failed": failed_dims,
                "ok": not failed_dims,
            }
        )

    metrics = {dim: _score_single(single[dim]) for dim in single}
    tools_metrics = _score_tools(tools_pairs)

    dim_score = {
        "task_type": metrics["task_type"]["accuracy"],
        "risk": metrics["risk"]["accuracy"],
        "complexity": metrics["complexity"]["accuracy"],
        "tools": tools_metrics["f1"],
        "output": metrics["output"]["accuracy"],
        "context": metrics["context"]["accuracy"],
        "approval": metrics["approval"]["accuracy"],
    }
    weighted = sum(GRADE_WEIGHTS[d] * dim_score[d] for d in GRADE_WEIGHTS)
    overall = round(100 * weighted / sum(GRADE_WEIGHTS.values()), 2)

    thresholds = {
        "overall_grade>=85": overall >= 85,
        "task_type_macro_f1>=0.90": metrics["task_type"]["macro_f1"] >= 0.90,
        "high_risk_recall==1.00": metrics["risk"]["per_class_recall"].get("high") == 1.0,
        "approval_accuracy==1.00": metrics["approval"]["accuracy"] == 1.0,
        "tool_f1>=0.90": tools_metrics["f1"] >= 0.90,
    }

    return {
        "n_cases": len(cases),
        "overall_grade": overall,
        "dimension_scores": {d: round(dim_score[d], 4) for d in dim_score},
        "grade_weights": GRADE_WEIGHTS,
        "task_type": metrics["task_type"],
        "complexity": metrics["complexity"],
        "risk": {
            **metrics["risk"],
            "high_risk_recall": metrics["risk"]["per_class_recall"].get("high"),
        },
        "tools": tools_metrics,
        "context": metrics["context"],
        "output": metrics["output"],
        "approval": metrics["approval"],
        "release_thresholds": thresholds,
        "release_ready": all(thresholds.values()),
        "failures": [c for c in per_case if not c["ok"]],
        "cases": per_case,
    }


def evaluate(gold_path: Path, classify_fn=classify) -> dict:
    return grade_cases(load_gold(gold_path), classify_fn)


# --- artifact writers --------------------------------------------------------


def write_artifacts(report: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "evaluation.json"
    md_path = out_dir / "evaluation.md"
    csv_path = out_dir / "failures.csv"

    slim = {k: v for k, v in report.items() if k != "cases"}
    json_path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "prompt", "dimension", "expected", "predicted"])
        for c in report["failures"]:
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
    return [json_path, md_path, csv_path]


# --- routing benchmark (Phase 3) --------------------------------------------

_PRICING_ORDER = [t.value for t in PricingTier]

# defaults for classification fields a routing scenario does not pin
_CLS_DEFAULTS = {
    "task_type": "coding",
    "complexity": "medium",
    "risk": "low",
    "context_tokens": 4000,
    "output_type": "code",
    "tool_needs": [],
}
_APPROVAL_BY_RISK = {"low": "auto", "medium": "notify", "high": "human-approval-required"}


def _band(tokens: int) -> str:
    if tokens < 8_000:
        return "small"
    return "medium" if tokens < 64_000 else "large"


def build_classification(d: dict) -> Classification:
    """Build a Classification from a partial scenario dict, filling defaults."""
    m = {**_CLS_DEFAULTS, **d}
    risk = m["risk"]
    return Classification(
        task_type=TaskType(m["task_type"]),
        complexity=Level(m["complexity"]),
        risk=Level(risk),
        context_tokens=m["context_tokens"],
        context_band=ContextBand(m.get("context_band") or _band(m["context_tokens"])),
        output_type=OutputType(m["output_type"]),
        tool_needs=list(m["tool_needs"]),
        approval_level=ApprovalLevel(m.get("approval_level") or _APPROVAL_BY_RISK[risk]),
    )


def _apply_pricing_cap(models: list[ModelEntry], cap: str | None) -> list[ModelEntry]:
    if not cap:
        return models
    ceiling = _PRICING_ORDER.index(cap)
    return [m for m in models if _PRICING_ORDER.index(m.pricing_tier.value) <= ceiling]


def grade_routing(scenarios: list[dict]) -> dict:
    """Grade routing scenarios over synthetic registries. Returns a report."""
    results = []
    for s in scenarios:
        models = [ModelEntry(**m) for m in s["models"]]
        cap = s.get("max_pricing_tier")
        capped = _apply_pricing_cap(models, cap)
        by_id = {m.model_id: m for m in models}
        cls = build_classification(s.get("classification", {}))
        r = engine_route(capped, cls)
        rec = r["recommendation"]
        fb = r["fallback"]
        excluded_ids = {e["model"].split("/", 1)[-1] for e in r["excluded"]}
        exp = s.get("expect", {})
        checks: dict[str, bool] = {}

        if "recommendation" in exp:
            checks["recommendation"] = rec is not None and rec["model_id"] == exp["recommendation"]
        if "fallback" in exp:
            acceptable = exp["fallback"] or []
            checks["fallback"] = (fb["model_id"] in acceptable) if fb else (acceptable == [])
        if "excluded" in exp:
            checks["excluded"] = all(mid in excluded_ids for mid in exp["excluded"])
        if exp.get("no_eligible"):
            checks["no_eligible"] = rec is None
        if cap:  # pricing cap is never exceeded
            checks["pricing_cap"] = rec is None or (
                _PRICING_ORDER.index(by_id[rec["model_id"]].pricing_tier.value)
                <= _PRICING_ORDER.index(cap)
            )
        # a retired model must never be recommended
        if rec is not None:
            checks["no_retired_win"] = by_id[rec["model_id"]].deprecation_status.value != "retired"

        results.append(
            {
                "id": s.get("id"),
                "description": s.get("description", ""),
                "checks": checks,
                "ok": all(checks.values()),
            }
        )

    passed = sum(r["ok"] for r in results)
    return {
        "n_scenarios": len(results),
        "passed": passed,
        "all_pass": passed == len(results),
        "scenarios": results,
        "failures": [r for r in results if not r["ok"]],
    }


def evaluate_routing(gold_path: Path) -> dict:
    doc = yaml.safe_load(gold_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("scenarios"), list):
        raise GoldError(f"{gold_path}: expected a mapping with a 'scenarios' list")
    return grade_routing(doc["scenarios"])


def _render_markdown(report: dict) -> str:
    r = report
    lines = [
        "# Classifier Evaluation Report",
        "",
        f"- Cases: **{r['n_cases']}**",
        f"- Overall grade: **{r['overall_grade']} / 100**",
        f"- Release-ready: **{'YES' if r['release_ready'] else 'NO'}**",
        "",
        "## Dimension scores (weighted into the grade)",
        "",
        "| Dimension | Weight | Score | Accuracy | Macro F1 |",
        "|---|---|---|---|---|",
    ]
    acc = {
        "task_type": r["task_type"]["accuracy"],
        "risk": r["risk"]["accuracy"],
        "complexity": r["complexity"]["accuracy"],
        "tools": r["tools"]["f1"],
        "output": r["output"]["accuracy"],
        "context": r["context"]["accuracy"],
        "approval": r["approval"]["accuracy"],
    }
    mf1 = {
        "task_type": r["task_type"]["macro_f1"],
        "risk": r["risk"]["macro_f1"],
        "complexity": r["complexity"]["macro_f1"],
    }
    for d, w in r["grade_weights"].items():
        lines.append(f"| {d} | {w} | {r['dimension_scores'][d]} | {acc[d]} | {mf1.get(d, '-')} |")
    lines += [
        "",
        "## Key metrics",
        "",
        f"- Task-type macro F1: **{r['task_type']['macro_f1']}**",
        f"- High-risk recall: **{r['risk']['high_risk_recall']}**",
        f"- Risk per-class recall: {r['risk']['per_class_recall']}",
        f"- Tool precision / recall / F1: "
        f"{r['tools']['precision']} / {r['tools']['recall']} / {r['tools']['f1']}",
        f"- Approval accuracy: **{r['approval']['accuracy']}**",
        "",
        "## Release thresholds",
        "",
        "| Threshold | Met |",
        "|---|---|",
    ]
    for name, ok in r["release_thresholds"].items():
        lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} |")
    lines += ["", f"## Failed cases ({len(r['failures'])})", ""]
    if not r["failures"]:
        lines.append("_None._")
    else:
        lines += ["| id | prompt | failed dimensions |", "|---|---|---|"]
        for c in r["failures"]:
            dims = ", ".join(
                f"{fd['dim']}(exp {fd['expected']} got {fd['predicted']})" for fd in c["failed"]
            )
            prompt = c["prompt"].replace("|", "\\|")
            lines.append(f"| {c['id']} | {prompt} | {dims} |")
    return "\n".join(lines) + "\n"
