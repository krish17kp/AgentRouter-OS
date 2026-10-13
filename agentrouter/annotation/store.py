"""Load/save the annotation program's artifacts with stable, hashable encodings.

YAML for human-facing datasets (candidates, adjudicated items) so reviewers can
read and edit them; the dataset SHA in the manifest is computed over a canonical
JSON encoding so it is independent of YAML formatting. All writers sort keys and
emit deterministic output for reproducible versioning.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from .schema import AdjudicatedItem, Candidate, DatasetManifest, ItemLabels


def _canonical(items: list[AdjudicatedItem]) -> str:
    """Formatting-independent canonical encoding used for the split SHA."""
    payload = [i.model_dump(mode="json", exclude_none=True) for i in items]
    payload.sort(key=lambda d: d["id"])
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def split_sha256(items: list[AdjudicatedItem]) -> str:
    return hashlib.sha256(_canonical(items).encode("utf-8")).hexdigest()


def save_candidates(path: Path, candidates: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "context-band-candidates",
        "candidates": [c.model_dump(mode="json", exclude_none=True) for c in candidates],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_candidates(path: Path) -> list[Candidate]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [Candidate(**c) for c in raw.get("candidates", [])]


def save_labels(path: Path, items: list[ItemLabels]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSONL: one item's labels per line, append-friendly for an annotation session.
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item.model_dump(mode="json", exclude_none=True), sort_keys=True))
            fh.write("\n")


def load_labels(path: Path) -> list[ItemLabels]:
    out: list[ItemLabels] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(ItemLabels(**json.loads(line)))
    return out


def save_dataset(path: Path, items: list[AdjudicatedItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(items, key=lambda i: i.id)
    data = {
        "schema": "context-band-dataset",
        "items": [i.model_dump(mode="json", exclude_none=True) for i in ordered],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_dataset(path: Path) -> list[AdjudicatedItem]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [AdjudicatedItem(**i) for i in raw.get("items", [])]


def save_manifest(path: Path, manifest: DatasetManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def load_manifest(path: Path) -> DatasetManifest:
    return DatasetManifest(**json.loads(path.read_text(encoding="utf-8")))
