"""Learned context-band predictor (TASK-009 / decision A).

A small, explainable multinomial logistic-regression model over deterministic,
interpretable text features. Trained ONLY on the development split; the frozen
holdout is never used for fitting or selection. Runtime inference is pure Python
(no numpy, no sklearn, no network) and deterministic. The trained weights ship as
a packaged JSON artifact; when it is absent or low-confidence the caller falls
back to the rule-based estimator, so the model can never make routing worse than
the rules alone.

The feature extractor here is the single source of truth used by both training
and inference, so they can never drift.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

MODEL_FILE = "context_band_model_v1.json"
CLASSES = ("small", "medium", "large")

_TOKEN_RE = re.compile(r"(\d+)\s*k[\s-]*token", re.I)
_TOKEN_PLAIN_RE = re.compile(r"(\d{4,})\s*tokens?", re.I)
_QUANT_RE = re.compile(r"(\d[\d,]{1,})\s*(page|file|document|record|partition|source file)", re.I)
_ARTIFACT = (
    r"(?:codebase|repo|repository|module|files?|project|system|subsystem|endpoints?|package|"
    r"service|microservice|middleware|controller|handler|webhook|worker|parser|pipeline|scheduler|"
    r"runner|library|client|lifecycle|flow|sequence|implementation|integration|migration|schema|"
    r"configuration|deployment|dashboard|handbook|specification|document|codepath|tests?|suite|"
    r"aggregates|traces?|partitions?)"
)
_DEFINITE_RE = re.compile(
    r"\b(?:the|its|this|these|those|our|their)\s+(?:\w+\s+){0,3}" + _ARTIFACT, re.I
)
_EXISTING = re.compile(
    r"\b(existing|current|already|in use|used by|without changing|its\b|intermittent|cause of)",
    re.I,
)
_REVIEW = re.compile(
    r"\b(review|audit|investigate|refactor|migrate|inspect|examine|diagnose|trace|assess|evaluate|"
    r"modernize|harden|profile|reconcile|untangle|rework|maintainab)",
    re.I,
)
_PIPELINE = re.compile(
    r"\b(pipeline|etl|ingestion|warehouse|retrieval|vector d|data validation|data flow|aggregat|"
    r"partition)",
    re.I,
)
_CONCEPTUAL = re.compile(
    r"\b(explain|what makes|describe|outline|purpose of|define|workflow|useful\?)",
    re.I,
)
_NEW = re.compile(
    r"\b(a|an)\s+(?:\w+\s+){0,2}(demo|sample|new|disposable|heading|snippet|prototype|scratch|toy|"
    r"example)",
    re.I,
)
_BIGCORPUS = re.compile(
    r"\b(entire|whole|complete|monorepo|corpus|archive|dossier|acquisition|compliance|year of|"
    r"thousands of|hundreds of)",
    re.I,
)
_DOCNOUN = re.compile(
    r"\b(document|report|filing|book|transcript|pdf|dossier|archive|specification|spec|protocol)",
    re.I,
)
_SELF = re.compile(r"\b(this sentence|these words|the following|below)\b", re.I)

FEATURES = (
    "explicit_ktoken",
    "explicit_tokens",
    "big_quantity",
    "definite_existing",
    "existing_marker",
    "review_verb",
    "pipeline",
    "conceptual",
    "new_indefinite",
    "big_corpus",
    "doc_noun",
    "self_contained",
    "wc_short",
    "wc_long",
)


def _max_quant(text: str) -> int:
    best = 0
    for m in _QUANT_RE.finditer(text):
        best = max(best, int(m.group(1).replace(",", "")))
    return best


def feature_vector(prompt: str) -> list[float]:
    """Deterministic interpretable features for a prompt (order matches FEATURES)."""
    low = prompt.lower()
    wc = len(prompt.split())
    q = _max_quant(prompt)
    return [
        1.0 if _TOKEN_RE.search(prompt) else 0.0,
        1.0 if _TOKEN_PLAIN_RE.search(prompt) else 0.0,
        1.0 if q >= 200 else 0.0,
        1.0 if _DEFINITE_RE.search(prompt) else 0.0,
        1.0 if _EXISTING.search(low) else 0.0,
        1.0 if _REVIEW.search(low) else 0.0,
        1.0 if _PIPELINE.search(low) else 0.0,
        1.0 if _CONCEPTUAL.search(low) else 0.0,
        1.0 if _NEW.search(low) else 0.0,
        1.0 if _BIGCORPUS.search(low) else 0.0,
        1.0 if _DOCNOUN.search(low) else 0.0,
        1.0 if _SELF.search(low) else 0.0,
        1.0 if wc <= 6 else 0.0,
        1.0 if wc >= 12 else 0.0,
    ]


@dataclass(frozen=True)
class LearnedBandModel:
    features: tuple[str, ...]
    classes: tuple[str, ...]
    coef: tuple[tuple[float, ...], ...]  # [class][feature]
    intercept: tuple[float, ...]

    def predict(self, prompt: str) -> tuple[str, float]:
        """Return (band, confidence) where confidence is the top softmax probability."""
        x = feature_vector(prompt)
        logits = [
            self.intercept[c] + sum(self.coef[c][i] * x[i] for i in range(len(x)))
            for c in range(len(self.classes))
        ]
        hi = max(logits)
        exps = [math.exp(v - hi) for v in logits]
        total = sum(exps)
        probs = [e / total for e in exps]
        best = max(range(len(probs)), key=lambda c: probs[c])
        return self.classes[best], probs[best]


def _validate(raw: dict) -> LearnedBandModel:
    features = tuple(raw["features"])
    classes = tuple(raw["classes"])
    coef = tuple(tuple(float(w) for w in row) for row in raw["coef"])
    intercept = tuple(float(v) for v in raw["intercept"])
    if features != FEATURES:
        raise ValueError("context-band model features do not match the code feature extractor")
    if classes != CLASSES or len(coef) != len(classes) or len(intercept) != len(classes):
        raise ValueError("context-band model shape is invalid")
    if any(len(row) != len(features) for row in coef):
        raise ValueError("context-band model coefficient width mismatch")
    return LearnedBandModel(features, classes, coef, intercept)


@lru_cache(maxsize=1)
def load_model() -> LearnedBandModel | None:
    """Load the packaged model, or None if absent/invalid (caller uses rules)."""
    try:
        raw = json.loads(
            (resources.files("agentrouter.benchmarks") / MODEL_FILE).read_text(encoding="utf-8")
        )
        return _validate(raw)
    except (FileNotFoundError, ModuleNotFoundError, KeyError, TypeError, ValueError,
            json.JSONDecodeError):
        return None
