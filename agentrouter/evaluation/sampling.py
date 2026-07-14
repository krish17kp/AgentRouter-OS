"""Deterministic sampling (program §5 requirement).

Seed-stable, order-independent subset selection. No RNG state, no Math.random
surprises: we hash (seed, key) and take the smallest N. Same inputs → same
sample on every machine and Python version.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def _rank(seed: int, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def deterministic_sample(items: list[T], limit: int, seed: int, key: Callable[[T], str]) -> list[T]:
    """Return `limit` items chosen deterministically by hashed rank of their key.

    Preserves the original relative order of the chosen items so reports read
    naturally. Stable across platforms because it uses sha256, not hash().
    """
    if limit <= 0:
        return []
    if limit >= len(items):
        return list(items)
    ranked = sorted(range(len(items)), key=lambda i: _rank(seed, key(items[i])))
    chosen = set(ranked[:limit])
    return [items[i] for i in range(len(items)) if i in chosen]
