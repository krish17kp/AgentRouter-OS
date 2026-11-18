"""Compare rules / learned / hybrid context-band predictors on a labelled split.

Metrics: accuracy, macro-F1, per-band recall, a bootstrap CI for accuracy, and
expected calibration error (ECE) over the reported confidences. Abstained dataset
items are excluded from accuracy and reported separately. This module only
*measures*; it never changes classifier rules, thresholds, or the release gate,
and it is only ever pointed at the new dev split — never the frozen holdout.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

from .. import classifier, context_model
from ..schema import ContextBand
from .schema import AdjudicatedItem

_LABEL_TO_BAND = {b.value: b for b in ContextBand}
STRATEGIES = ("rules", "learned", "hybrid")
DEFAULT_HYBRID_THRESHOLD = 0.6


@dataclass(frozen=True)
class Prediction:
    band: ContextBand
    confidence: float
    used_rules_fallback: bool


def _rules_band(prompt: str) -> ContextBand:
    # Shipped default is rules-active, so classify() yields the rule band. Guard it
    # so a flipped flag can't silently turn this baseline into the hybrid. A raise
    # (not assert) keeps the guard under `python -O`.
    if classifier._USE_LEARNED_BAND is not False:
        raise RuntimeError("rules baseline requires classifier._USE_LEARNED_BAND is False")
    return classifier.classify(prompt).context_band


def predict(
    prompt: str, strategy: str, *, threshold: float = DEFAULT_HYBRID_THRESHOLD
) -> Prediction:
    rb = _rules_band(prompt)
    if strategy == "rules":
        return Prediction(rb, 1.0, used_rules_fallback=True)

    model = context_model.load_model()
    if model is None:  # learned artifact absent -> rules everywhere (honest)
        return Prediction(rb, 0.0, used_rules_fallback=True)
    label, conf = model.predict(prompt)
    lb = _LABEL_TO_BAND[label]
    if strategy == "learned":
        return Prediction(lb, conf, used_rules_fallback=False)
    if strategy == "hybrid":
        if conf >= threshold:
            return Prediction(lb, conf, used_rules_fallback=False)
        return Prediction(rb, conf, used_rules_fallback=True)
    raise ValueError(f"unknown strategy {strategy!r}")


def _macro_f1(gold: list[ContextBand], pred: list[ContextBand]) -> float:
    f1s = []
    for band in ContextBand:
        tp = sum(1 for g, p in zip(gold, pred, strict=True) if g == band and p == band)
        fp = sum(1 for g, p in zip(gold, pred, strict=True) if g != band and p == band)
        fn = sum(1 for g, p in zip(gold, pred, strict=True) if g == band and p != band)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    return sum(f1s) / len(f1s)


def _per_band_recall(gold: list[ContextBand], pred: list[ContextBand]) -> dict[str, float]:
    out: dict[str, float] = {}
    for band in ContextBand:
        support = sum(1 for g in gold if g == band)
        hit = sum(1 for g, p in zip(gold, pred, strict=True) if g == band and p == band)
        out[band.value] = round(hit / support, 4) if support else None
    return out


def _bootstrap_acc_ci(
    gold: list[ContextBand], pred: list[ContextBand], *, n: int = 2000, seed: int = 20260731
) -> tuple[float, float]:
    if not gold:
        return (0.0, 0.0)
    rng = random.Random(seed)  # nosec B311 - bootstrap resampling, not security
    m = len(gold)
    accs = []
    for _ in range(n):
        idx = [rng.randrange(m) for _ in range(m)]
        accs.append(sum(1 for i in idx if gold[i] == pred[i]) / m)
    accs.sort()
    lo = accs[int(0.025 * n)]
    hi = accs[min(n - 1, int(0.975 * n))]
    return (round(lo, 4), round(hi, 4))


def _ece(
    gold: list[ContextBand], pred: list[ContextBand], conf: list[float], bins: int = 10
) -> float:
    """Expected calibration error over confidence bins."""
    if not gold:
        return 0.0
    buckets: dict[int, list[int]] = defaultdict(list)
    for i, c in enumerate(conf):
        b = min(bins - 1, int(c * bins))
        buckets[b].append(i)
    total = len(gold)
    ece = 0.0
    for idxs in buckets.values():
        acc = sum(1 for i in idxs if gold[i] == pred[i]) / len(idxs)
        avg_conf = sum(conf[i] for i in idxs) / len(idxs)
        ece += (len(idxs) / total) * abs(acc - avg_conf)
    return round(ece, 4)


@dataclass
class StrategyReport:
    strategy: str
    n: int
    accuracy: float
    macro_f1: float
    per_band_recall: dict
    acc_ci95: tuple[float, float]
    ece: float
    rules_fallback_rate: float
    abstained_items: int = 0


def evaluate(
    items: list[AdjudicatedItem], strategy: str, *, threshold: float = DEFAULT_HYBRID_THRESHOLD
) -> StrategyReport:
    banded = [i for i in items if not i.abstained and i.band is not None]
    gold = [i.band for i in banded]
    preds = [predict(i.prompt, strategy, threshold=threshold) for i in banded]
    pred_bands = [p.band for p in preds]
    conf = [p.confidence for p in preds]
    n = len(banded)
    acc = (
        round(sum(1 for g, p in zip(gold, pred_bands, strict=True) if g == p) / n, 4) if n else 0.0
    )
    return StrategyReport(
        strategy=strategy,
        n=n,
        accuracy=acc,
        macro_f1=round(_macro_f1(gold, pred_bands), 4),
        per_band_recall=_per_band_recall(gold, pred_bands),
        acc_ci95=_bootstrap_acc_ci(gold, pred_bands),
        ece=_ece(gold, pred_bands, conf),
        rules_fallback_rate=round(sum(1 for p in preds if p.used_rules_fallback) / n, 4)
        if n
        else 0.0,
        abstained_items=sum(1 for i in items if i.abstained),
    )


def compare_all(
    items: list[AdjudicatedItem], *, threshold: float = DEFAULT_HYBRID_THRESHOLD
) -> dict[str, StrategyReport]:
    return {s: evaluate(items, s, threshold=threshold) for s in STRATEGIES}
