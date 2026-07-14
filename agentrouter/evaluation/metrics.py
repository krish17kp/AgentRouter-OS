"""Classification metrics over normalized EvaluationCases (program §6.1).

Acceptable-set grading: a prediction is correct if it lands in the case's
acceptable set for that dimension. Dimensions with an empty expected set are
skipped (not counted against the model). High-risk recall is surfaced on its
own because it is a release gate.
"""

from __future__ import annotations

from collections import defaultdict

from ..classifier import classify
from .schema import EvaluationCase

_SINGLE_DIMS = ("task_type", "complexity", "risk", "output", "context", "approval")


def _predict(case: EvaluationCase, classify_fn) -> dict:
    c = classify_fn(case.task)
    return {
        "task_type": c.task_type.value,
        "complexity": c.complexity.value,
        "risk": c.risk.value,
        "output": c.output_type.value,
        "context": c.context_band.value,
        "approval": c.approval_level.value,
        "tools": set(c.tool_needs),
    }


def _expected_sets(case: EvaluationCase) -> dict:
    e = case.expected
    return {
        "task_type": [x.value for x in e.task_types],
        "complexity": [x.value for x in e.complexities],
        "risk": [x.value for x in e.risks],
        "output": [x.value for x in e.output_types],
        "context": [x.value for x in e.context_bands],
        "approval": [x.value for x in e.approval_levels],
        "tools": set(e.required_tools),
    }


def _score_single(pairs: list[tuple[list[str], str]]) -> dict:
    """Accuracy + macro-F1 + per-class recall for one single-label dimension."""
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
    tp = fp = fn = exact = 0
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


def _confusion(pairs: list[tuple[list[str], str]]) -> dict[str, dict[str, int]]:
    """gold(first acceptable)->predicted counts. Only over graded pairs."""
    mat: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for acceptable, pred in pairs:
        gold = pred if pred in acceptable else acceptable[0]
        mat[gold][pred] += 1
    return {g: dict(row) for g, row in mat.items()}


def classification_metrics(cases: list[EvaluationCase], classify_fn=classify) -> dict:
    """Full classification report + per-case failures over a case list."""
    single: dict[str, list[tuple[list[str], str]]] = {d: [] for d in _SINGLE_DIMS}
    tools_pairs: list[tuple[set[str], set[str]]] = []
    failures: list[dict] = []

    for case in cases:
        pred = _predict(case, classify_fn)
        exp = _expected_sets(case)
        failed: list[dict] = []
        for d in _SINGLE_DIMS:
            if exp[d]:
                single[d].append((exp[d], pred[d]))
                if pred[d] not in exp[d]:
                    failed.append({"dim": d, "expected": exp[d], "predicted": pred[d]})
        if case.expected.required_tools or pred["tools"]:
            tools_pairs.append((exp["tools"], pred["tools"]))
            if exp["tools"] != pred["tools"]:
                failed.append(
                    {
                        "dim": "tools",
                        "expected": sorted(exp["tools"]),
                        "predicted": sorted(pred["tools"]),
                    }
                )
        if failed:
            failures.append({"id": case.id, "prompt": case.task, "failed": failed})

    report = {d: _score_single(single[d]) for d in _SINGLE_DIMS}
    report["tools"] = _score_tools(tools_pairs)
    report["confusion_task_type"] = _confusion(single["task_type"])
    report["confusion_risk"] = _confusion(single["risk"])
    report["high_risk_recall"] = report["risk"]["per_class_recall"].get("high")
    report["n_cases"] = len(cases)
    report["failures"] = failures
    return report
