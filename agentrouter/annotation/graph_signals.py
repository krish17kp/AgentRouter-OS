"""Optional Graphify-derived repository-impact signal (TASK-011).

When a prompt names real repository artifacts (modules, files), the size of the
affected dependency neighbourhood is weak evidence for a larger context band. This
reads a Graphify ``graph.json`` if one is present and returns a bounded impact
score; when the graph is absent or unreadable it returns a text-only fallback so
the pipeline never depends on Graphify. This is an *optional feature*, never a
label and never required for basic operation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DEFAULT_GRAPH = Path("graphify-out") / "graph.json"
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{2,}")


@dataclass(frozen=True)
class ImpactSignal:
    available: bool  # False -> text-only fallback (graph absent)
    matched_nodes: int
    dependency_reach: int  # matched nodes + their direct neighbours

    @property
    def feature(self) -> float:
        """Bounded [0,1] impact feature; 0.0 when unavailable (text-only)."""
        if not self.available:
            return 0.0
        # saturating: a handful of reached nodes already implies broad context
        return min(1.0, self.dependency_reach / 20.0)


@lru_cache(maxsize=4)
def _load_graph(path_str: str) -> tuple[frozenset[str], dict[str, tuple[str, ...]]] | None:
    path = Path(path_str)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return None
    nodes = raw.get("nodes") or []
    names: set[str] = set()
    for n in nodes:
        for key in ("name", "id", "label", "file"):
            v = n.get(key) if isinstance(n, dict) else None
            if isinstance(v, str) and v:
                names.add(v.split("/")[-1].split(".")[0].lower())
    adj: dict[str, tuple[str, ...]] = {}
    for e in raw.get("edges") or raw.get("links") or []:
        if not isinstance(e, dict):
            continue
        s, t = e.get("source"), e.get("target")
        if isinstance(s, str) and isinstance(t, str):
            adj.setdefault(s.lower(), tuple())
            adj[s.lower()] = adj[s.lower()] + (t.lower(),)
    return frozenset(names), adj


def impact_for(prompt: str, graph_path: Path | str = _DEFAULT_GRAPH) -> ImpactSignal:
    """Best-effort repository-impact signal for a prompt; graceful when no graph."""
    loaded = _load_graph(str(graph_path))
    if loaded is None:
        return ImpactSignal(available=False, matched_nodes=0, dependency_reach=0)
    names, adj = loaded
    tokens = {t.lower() for t in _WORD.findall(prompt)}
    matched = tokens & names
    reach = set(matched)
    for m in matched:
        reach.update(adj.get(m, ()))
    return ImpactSignal(available=True, matched_nodes=len(matched), dependency_reach=len(reach))
