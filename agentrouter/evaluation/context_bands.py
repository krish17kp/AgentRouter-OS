"""Held-out context-band generalization measurement (TASK-009).

The development and final-holdout sets are separate package resources. The final file is frozen by
SHA-256 and is not imported into classifier unit-test parametrizations. Metrics are descriptive;
this module never changes classifier rules or thresholds.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

from .. import classifier
from ..schema import ContextBand
from .base import gold_path

DEV_FILE = "context_band_dev_v1.yaml"
HOLDOUT_FILE = "context_band_holdout_v1.yaml"
HOLDOUT_SHA256 = "ca07dfa09f08cd877d383067b8e1163c0f196a5a1f0c4e641adefed12b17508f"
BANDS = tuple(b.value for b in ContextBand)
REQUIRED_CATEGORIES = frozenset(
    {
        "coding",
        "review",
        "audit",
        "refactor",
        "documentation",
        "analysis",
        "summarization",
        "data-pipeline",
        "ambiguous",
    }
)

# Historical comparator copied from the pre-TASK-004 implementation. Keep these
# literals local: importing live classifier matchers would silently rewrite history
# whenever the production classifier changes.
_LEGACY_TOKEN_RE = re.compile(r"(\d+)\s*k[\s-]*token", re.IGNORECASE)
_LEGACY_TOKEN_PLAIN_RE = re.compile(r"(\d{4,})[\s-]*token", re.IGNORECASE)


def _legacy_matcher(words: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(re.escape(word) for word in words) + r")\b", re.IGNORECASE)


_LEGACY_DOCUMENT = _legacy_matcher(("document", "report", "filing", "book", "transcript", "pdf"))
_LEGACY_EXISTING_CODE = _legacy_matcher(
    (
        "codebase",
        "repo",
        "repository",
        "module",
        "files",
        "project",
        "system",
        "endpoint",
        "endpoints",
        "package",
        "service",
        "microservice",
        "middleware",
        "controller",
        "handler",
        "webhook",
        "worker",
        "parser",
        "api",
        "migration",
        "pull request",
        "test coverage",
        "coverage",
        "the auth",
        "the payment",
    )
)


@dataclass(frozen=True)
class ContextBandCase:
    id: str
    prompt: str
    context_band: str
    category: str


def _sha256(path: Path) -> str:
    # Canonicalize newlines so Git's Windows checkout policy cannot invalidate the freeze lock.
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cases(filename: str) -> list[ContextBandCase]:
    path = gold_path(filename)
    if filename == HOLDOUT_FILE and _sha256(path) != HOLDOUT_SHA256:
        raise ValueError(
            "frozen context-band holdout checksum changed; version the dataset and review it"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise ValueError(f"invalid context-band dataset: {path}")
    cases = [ContextBandCase(**item) for item in raw["cases"]]
    ids = [case.id for case in cases]
    prompts = [_normalize(case.prompt) for case in cases]
    if len(ids) != len(set(ids)) or len(prompts) != len(set(prompts)):
        raise ValueError(f"duplicate id or prompt in context-band dataset: {path}")
    invalid = [case.id for case in cases if case.context_band not in BANDS]
    if invalid:
        raise ValueError(f"unknown context band in cases: {', '.join(invalid)}")
    return cases


def load_development() -> list[ContextBandCase]:
    return load_cases(DEV_FILE)


def load_holdout() -> list[ContextBandCase]:
    cases = load_cases(HOLDOUT_FILE)
    categories = {case.category for case in cases}
    missing = REQUIRED_CATEGORIES - categories
    if missing:
        raise ValueError(f"holdout is missing required categories: {', '.join(sorted(missing))}")
    return cases


def _normalize(text: str) -> str:
    compact = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"[^\w\s]", "", compact)


def prompt_similarity(left: str, right: str) -> dict[str, float]:
    """Character-sequence and token-set similarity for cross-split leakage checks."""
    a, b = _normalize(left), _normalize(right)
    at, bt = set(a.split()), set(b.split())
    jaccard = len(at & bt) / len(at | bt) if at or bt else 1.0
    return {"sequence": SequenceMatcher(None, a, b).ratio(), "token_jaccard": jaccard}


def cross_split_leaks(
    holdout: list[ContextBandCase], references: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """Find exact or near-identical holdout prompts in named reference collections."""
    leaks: list[dict[str, Any]] = []
    for case in holdout:
        normalized = _normalize(case.prompt)
        for source, prompts in references.items():
            for prompt in prompts:
                other = _normalize(prompt)
                scores = prompt_similarity(case.prompt, prompt)
                min_words = min(len(normalized.split()), len(other.split()))
                exact = normalized == other
                near = min_words >= 3 and (
                    scores["sequence"] >= 0.88 or scores["token_jaccard"] >= 0.82
                )
                if exact or near:
                    leaks.append(
                        {
                            "holdout_id": case.id,
                            "source": source,
                            "exact": exact,
                            **{k: round(v, 4) for k, v in scores.items()},
                        }
                    )
    return leaks


def _predict_band(predictor, prompt: str) -> str:
    predicted = predictor(prompt)
    if hasattr(predicted, "context_band"):
        predicted = predicted.context_band
    if hasattr(predicted, "value"):
        predicted = predicted.value
    value = str(predicted)
    if value not in BANDS:
        raise ValueError(f"predictor returned unknown context band: {value}")
    return value


def _wilson(successes: int, total: int, z: float = 1.96) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def _metric_values(pairs: list[tuple[str, str]]) -> tuple[float, float, dict[str, float]]:
    tp: Counter[str] = Counter()
    fp: Counter[str] = Counter()
    fn: Counter[str] = Counter()
    for expected, predicted in pairs:
        if expected == predicted:
            tp[expected] += 1
        else:
            fn[expected] += 1
            fp[predicted] += 1
    recalls: dict[str, float] = {}
    f1s: list[float] = []
    for band in BANDS:
        precision = tp[band] / (tp[band] + fp[band]) if tp[band] + fp[band] else 0.0
        recall = tp[band] / (tp[band] + fn[band]) if tp[band] + fn[band] else 0.0
        recalls[band] = recall
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    accuracy = sum(expected == predicted for expected, predicted in pairs) / len(pairs)
    return accuracy, sum(f1s) / len(f1s), recalls


def _bootstrap_macro_f1(
    pairs: list[tuple[str, str]], samples: int = 2000, seed: int = 1729
) -> list[float]:
    rng = random.Random(seed)  # nosec B311 - bootstrap CI resampling, deterministic seed, not crypto
    values: list[float] = []
    for _ in range(samples):
        sampled = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        values.append(_metric_values(sampled)[1])
    values.sort()
    return [round(values[int(0.025 * samples)], 4), round(values[int(0.975 * samples) - 1], 4)]


def score(cases: list[ContextBandCase], predictor=classifier.classify) -> dict[str, Any]:
    pairs: list[tuple[str, str]] = []
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    failures: list[dict[str, str]] = []
    by_category: dict[str, list[bool]] = defaultdict(list)
    for case in cases:
        predicted = _predict_band(predictor, case.prompt)
        pairs.append((case.context_band, predicted))
        confusion[case.context_band][predicted] += 1
        correct = predicted == case.context_band
        by_category[case.category].append(correct)
        if not correct:
            failures.append(
                {
                    "id": case.id,
                    "category": case.category,
                    "expected": case.context_band,
                    "predicted": predicted,
                }
            )
    accuracy, macro_f1, recalls = _metric_values(pairs)
    band_counts = Counter(expected for expected, _ in pairs)
    band_correct = Counter(expected for expected, predicted in pairs if expected == predicted)
    return {
        "n": len(cases),
        "accuracy": round(accuracy, 4),
        "accuracy_ci95": _wilson(len(cases) - len(failures), len(cases)),
        "macro_f1": round(macro_f1, 4),
        "macro_f1_bootstrap_ci95": _bootstrap_macro_f1(pairs),
        "per_band_recall": {band: round(recalls[band], 4) for band in BANDS},
        "per_band_recall_ci95": {
            band: _wilson(band_correct[band], band_counts[band]) for band in BANDS
        },
        "category_accuracy": {
            name: round(sum(values) / len(values), 4)
            for name, values in sorted(by_category.items())
        },
        "confusion": {band: dict(confusion[band]) for band in BANDS},
        "failures": failures,
    }


def legacy_pre_task004_band(prompt: str) -> str:
    """Frozen reference for `_context_tokens` immediately before TASK-004."""
    text = prompt.lower()
    match = _LEGACY_TOKEN_RE.search(text)
    if match:
        tokens = int(match.group(1)) * 1000
    else:
        match = _LEGACY_TOKEN_PLAIN_RE.search(text)
        if match:
            tokens = int(match.group(1))
        elif _LEGACY_DOCUMENT.search(text):
            tokens = 30000
        elif _LEGACY_EXISTING_CODE.search(text):
            tokens = 12000
        else:
            tokens = 2000
    if tokens < 8_000:
        return "small"
    if tokens < 64_000:
        return "medium"
    return "large"


def evaluate_generalization() -> dict[str, Any]:
    development = load_development()
    holdout = load_holdout()
    before = score(holdout, legacy_pre_task004_band)
    current = score(holdout, classifier.classify)
    return {
        "schema_version": 1,
        "holdout_sha256": HOLDOUT_SHA256,
        "development": score(development, classifier.classify),
        "pre_task004_holdout": before,
        "current_holdout": current,
        "delta": {
            "accuracy": round(current["accuracy"] - before["accuracy"], 4),
            "macro_f1": round(current["macro_f1"] - before["macro_f1"], 4),
        },
        "limitations": [
            "The holdout is public and model-assisted, pending independent human review.",
            "Context-band labels infer required input size from short prompts without real files.",
            "Confidence intervals quantify sample uncertainty, not annotation uncertainty.",
        ],
    }
