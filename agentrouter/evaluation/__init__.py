"""AgentRouter OS evaluation framework.

Normalized evaluation cases, dataset adapters, metrics, a 100-point grade and
release gates. Heavy dependencies (datasets, pandas, sklearn, mlflow, dvc) are
optional extras — the core framework and all fixture-backed tests run offline
with only the base runtime deps.
"""

from .schema import EvaluationCase, ExpectedClassification, Provenance

__all__ = ["EvaluationCase", "ExpectedClassification", "Provenance"]
