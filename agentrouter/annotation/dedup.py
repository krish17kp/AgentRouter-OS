"""Exact and near-duplicate detection + cross-split leakage checks (TASK-011).

Pure stdlib. Two prompts are:
  * exact duplicates when their normalised forms are identical;
  * near duplicates when their word-shingle Jaccard similarity >= NEAR_THRESHOLD.

Used both to cluster within a candidate pool (so near-duplicates never straddle
a train/dev/holdout boundary) and to prove a new split does not leak against the
frozen holdout or any other literal set. Checking for leakage against the frozen
holdout is allowed and required; it is not tuning against it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher

NEAR_THRESHOLD = 0.8
_SHINGLE = 3  # words per shingle
_NON_WORD = re.compile(r"[^a-z0-9\s]+")
_WS = re.compile(r"\s+")


def normalize(prompt: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — the exact-dup key."""
    low = _NON_WORD.sub(" ", prompt.lower())
    return _WS.sub(" ", low).strip()


def _shingles(prompt: str) -> frozenset[str]:
    words = normalize(prompt).split()
    if len(words) < _SHINGLE:
        # short prompts: the whole normalised string is the single shingle
        return frozenset({" ".join(words)}) if words else frozenset()
    return frozenset(" ".join(words[i : i + _SHINGLE]) for i in range(len(words) - _SHINGLE + 1))


def _shingle_jaccard(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def similarity(a: str, b: str) -> float:
    """Near-duplicate similarity in [0, 1].

    The max of word-shingle Jaccard (robust to reordering / large paraphrase) and
    a normalised edit ratio (robust to single-word swaps in short prompts). Taking
    the max makes this a *sensitive* leakage guard: it errs toward flagging.
    """
    na, nb = normalize(a), normalize(b)
    edit_ratio = SequenceMatcher(None, na, nb).ratio()
    return max(_shingle_jaccard(a, b), edit_ratio)


@dataclass(frozen=True)
class Duplicate:
    left: str
    right: str
    kind: str  # "exact" | "near"
    score: float


def cluster(prompts: Iterable[str], threshold: float = NEAR_THRESHOLD) -> list[list[int]]:
    """Group prompt indices into duplicate clusters (union-find over near-dups).

    Prompts in the same cluster must be kept within one split so a train item and
    its near-duplicate cannot leak into dev/holdout.
    """
    items = list(prompts)
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    norms = [normalize(p) for p in items]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if norms[i] == norms[j] or similarity(items[i], items[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def find_leakage(
    candidate: Iterable[str],
    reference: Iterable[str],
    threshold: float = NEAR_THRESHOLD,
) -> list[Duplicate]:
    """Every candidate prompt that exactly- or near-duplicates a reference prompt.

    Use with the frozen-holdout prompts as ``reference`` to prove isolation.
    """
    refs = list(reference)
    ref_norms = [normalize(r) for r in refs]
    found: list[Duplicate] = []
    for c in candidate:
        cn = normalize(c)
        for r, rn in zip(refs, ref_norms, strict=True):
            if cn == rn:
                found.append(Duplicate(c, r, "exact", 1.0))
                continue
            s = similarity(c, r)
            if s >= threshold:
                found.append(Duplicate(c, r, "near", round(s, 3)))
    return found
