"""Deterministic candidate-prompt generation for human annotation (TASK-011).

Generates diverse, UNLABELLED prompts across every required category and a range
of implied scopes (self-contained one-liners, work on existing artifacts, and
large-corpus tasks). It never assigns a context band — a human reviewer does that
later. Generation is seeded and reproducible, uses no network or LLM, and tags
each item with its template so provenance is auditable.

The scope hints below shape prompt *wording* only; they are NOT labels. A prompt
built from the "large" phrase bank may still be judged medium by a human, which
is exactly the ambiguity the dataset must capture.
"""

from __future__ import annotations

import random

from .schema import Candidate

# Per-category surface realisations at three implied scopes. Deliberately varied
# vocabulary and syntax so the pool is not trivially separable by one keyword.
_BANKS: dict[str, dict[str, list[str]]] = {
    "coding": {
        "small": [
            "Produce a helper that rounds a timestamp down to the nearest minute.",
            "Give me a one-liner that flattens a list of lists.",
            "Draft a small class representing an RGB color.",
        ],
        "existing": [
            "Attach a circuit breaker to the payment gateway wrapper we already ship.",
            "Correct the timezone bug in the scheduling module currently in production.",
            "Thread a correlation id through the order-processing service that exists today.",
        ],
        "large": [
            "Introduce soft-delete semantics on every entity across the billing platform.",
            "Roll optimistic concurrency into all mutating endpoints of our storefront backend.",
        ],
    },
    "review": {
        "small": [
            "In one line, what signals a risky pull request?",
            "List two reasons small diffs get reviewed faster.",
        ],
        "existing": [
            "Go over the open merge request and note anything that hurts long-term upkeep.",
            "Assess the queued fix for edge cases the author probably missed.",
        ],
        "large": [
            "Walk the complete billing engine and surface any newly introduced auth weaknesses.",
            "Vet every schema change in the project for steps that cannot be rolled back.",
        ],
    },
    "refactor": {
        "small": [
            "In brief, when is it safe to rename a public symbol?",
            "Name one smell that suggests splitting a function.",
        ],
        "existing": [
            "Rework the alerts module so its outward behavior stays identical.",
            "Bring the legacy billing widget up to date without changing its public contract.",
        ],
        "large": [
            "Reorganize a checked-out tree of roughly twelve hundred modules for clarity.",
            "Break the tangled import cycles spanning our entire multi-package workspace.",
        ],
    },
    "documentation": {
        "small": [
            "Propose a heading for the quick-start section.",
            "Draft a tagline for a small logging utility.",
        ],
        "existing": [
            "Write API docs describing what the shipped serializer actually outputs today.",
            "Explain, for operators, the path a job takes through the queue we run now.",
        ],
        "large": [
            "Author a full runbook covering every stage of our multi-region rollout.",
            "Draft complete developer guides for all public routes in the product surface.",
        ],
    },
    "summarization": {
        "small": [
            "Trim this heading to five words.",
            "Give a one-sentence gist of a cron job's purpose.",
        ],
        "existing": [
            "Collapse the current on-call playbook into a single printable page.",
            "Pull the key rulings out of the meeting minutes I pasted.",
        ],
        "large": [
            "Digest a 90k-token bundle of vendor contracts into a risk list.",
            "Boil down a decade of release notes into recurring themes.",
        ],
    },
    "analysis": {
        "small": [
            "At a high level, contrast polling with webhooks.",
            "What is one downside of eager cache warming?",
        ],
        "existing": [
            "Judge whether the present backoff strategy risks synchronized retries.",
            "Weigh coupling between the current parser and its grammar fixtures.",
        ],
        "large": [
            "Comb 140k tokens of gateway access logs for anomalous session behavior.",
            "Trace the full checkout path end to end and rank where time is lost.",
        ],
    },
    "data-pipeline": {
        "small": [
            "Explain, briefly, what a dead-letter queue is for.",
            "In a sentence, what does a feature store provide?",
        ],
        "existing": [
            "Track down why rows vanish between the two current ingestion hops.",
            "Align mismatched column types between the live feed and the mart we maintain.",
        ],
        "large": [
            "Reconstruct the whole transformation DAG behind the analytics dashboards.",
            "Certify an entire year-partition of the lakehouse for downstream reporting.",
        ],
    },
    "rag": {
        "small": [
            "What problem does query expansion solve in retrieval?",
            "Outline a tiny prompt that cites a single passage.",
        ],
        "existing": [
            "Lift retrieval precision on the document index our assistant already queries.",
            "Attach source offsets to responses from the retrieval chain we run today.",
        ],
        "large": [
            "Architect search across an eight-million-record archive with staleness bounds.",
            "Anchor every answer in a sprawling internal wiki with traceable citations.",
        ],
    },
    "tool-use": {
        "small": [
            "When is a unit-conversion tool the right call for an agent?",
            "Sketch the argument schema for a single currency-quote tool.",
        ],
        "existing": [
            "Register one more capability into the agent toolbox we currently expose.",
            "Repair the parameter checks on the existing document-lookup tool.",
        ],
        "large": [
            "Sequence a many-tool automation covering our full deployment lifecycle.",
            "Coordinate a large fleet of tools across an end-to-end incident response.",
        ],
    },
    "ambiguous": {
        "small": [
            "Have a look.",
            "Clean up.",
            "Sort this.",
        ],
        "existing": [
            "Why is this behaving oddly?",
            "Make this nicer.",
        ],
        "large": [
            "Take care of the whole migration.",
            "Deal with all of it before launch.",
        ],
    },
}


def _all_unique() -> list[tuple[str, str, str]]:
    """Every distinct (category, scope, prompt) triple, in a stable order."""
    triples: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for scope in ("small", "existing", "large"):  # interleave scopes for balance
        for category in _BANKS:
            for prompt in _BANKS[category][scope]:
                if prompt not in seen:
                    seen.add(prompt)
                    triples.append((category, scope, prompt))
    return triples


def generate(count: int | None = None, *, seed: int = 20260731) -> list[Candidate]:
    """Return deterministic, UNLABELLED candidates spanning every category.

    Every prompt in the pool is distinct (no exact repeats). ``count`` caps the
    pool; when None (or larger than the bank), all unique candidates are returned.
    The seed only shuffles ordering, so IDs are stable for a given (count, seed).
    """
    triples = _all_unique()
    rng = random.Random(seed)
    rng.shuffle(triples)
    if count is not None:
        triples = triples[:count]
    return [
        Candidate(
            id=f"cand-{i + 1:04d}",
            prompt=prompt,
            category=category,
            source="generated_candidate",
            template=f"{category}/{scope}",
        )
        for i, (category, scope, prompt) in enumerate(triples)
    ]
