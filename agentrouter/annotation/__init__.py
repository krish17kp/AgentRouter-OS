"""Context-band data collection, annotation, adjudication and evaluation (TASK-011).

A self-contained program for building a *human-reviewed* context-band dataset and
a fresh private holdout, without reusing or tuning against the frozen TASK-009
holdout. Candidate prompts may be generated automatically, but every final label
is assigned by a human reviewer (or, in demo/pipeline runs, is explicitly flagged
as pending human review). Nothing here changes classifier rules, the learned
model runtime, the frozen holdout, or the 0.90 release gate.
"""

from __future__ import annotations

SCHEMA_VERSION = 1
CATEGORIES = (
    "coding",
    "review",
    "refactor",
    "documentation",
    "summarization",
    "analysis",
    "data-pipeline",
    "rag",
    "tool-use",
    "ambiguous",
)
SPLITS = ("train", "dev", "holdout")
