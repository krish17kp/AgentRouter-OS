"""`agentrouter dataset ...` — the context-band annotation program CLI (TASK-011).

Local, offline commands for the full pipeline: generate candidates, collect
per-annotator labels (interactive or batch), adjudicate disagreements, build
leakage-checked train/dev/holdout splits with a versioned manifest, and compare
rules/learned/hybrid on the new dev split. It never touches the frozen holdout
except to prove the new splits do not leak against it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from ..schema import ContextBand
from . import CATEGORIES
from . import candidates as candidates_mod
from .adjudicate import Adjudication, resolve
from .compare import compare_all
from .dedup import find_leakage
from .schema import AdjudicatedItem, AnnotatorLabel, DatasetManifest, ItemLabels
from .splits import partition
from .store import (
    load_candidates,
    load_dataset,
    load_labels,
    save_candidates,
    save_dataset,
    save_labels,
    save_manifest,
    split_sha256,
)

dataset_app = typer.Typer(help="Context-band data collection + annotation program (TASK-011).")

_FROZEN_HOLDOUT = "context_band_holdout_v1.yaml"
_BAND_CHOICE = {"s": ContextBand.small, "m": ContextBand.medium, "l": ContextBand.large}


def _frozen_holdout_prompts() -> list[str]:
    """Prompts only (never labels) from the frozen holdout, for leakage checks."""
    from importlib import resources

    try:
        raw = yaml.safe_load(
            (resources.files("agentrouter.benchmarks") / _FROZEN_HOLDOUT).read_text(
                encoding="utf-8"
            )
        )
    except (FileNotFoundError, ModuleNotFoundError, ValueError):
        return []
    return [c["prompt"] for c in (raw or {}).get("cases", []) if "prompt" in c]


@dataset_app.command("gen-candidates")
def gen_candidates(
    out: Path = typer.Option(..., "--out", help="Where to write the candidate pool YAML."),
    count: int = typer.Option(120, "--count", min=len(CATEGORIES)),
    seed: int = typer.Option(20260731, "--seed"),
):
    """Generate a deterministic, UNLABELLED candidate pool for human review."""
    pool = candidates_mod.generate(count, seed=seed)
    save_candidates(out, pool)
    typer.echo(f"Wrote {len(pool)} candidates to {out} (unlabelled; humans assign bands).")


@dataset_app.command("annotate")
def annotate(
    candidates_path: Path = typer.Argument(..., help="Candidate pool YAML."),
    annotator: str = typer.Option(..., "--annotator", help="Annotator id."),
    out: Path = typer.Option(..., "--out", help="Where to append this annotator's labels (JSONL)."),
):
    """Interactively label each candidate (band S/M/L, or 'a' to abstain)."""
    pool = load_candidates(candidates_path)
    items: list[ItemLabels] = []
    typer.echo(f"Annotating {len(pool)} candidates as '{annotator}'. Ctrl-C to stop.")
    for cand in pool:
        typer.echo(f"\n[{cand.category}] {cand.prompt}")
        choice = typer.prompt("band (s/m/l/a=abstain)").strip().lower()
        abstain = choice.startswith("a")
        band = None if abstain else _BAND_CHOICE.get(choice)
        if not abstain and band is None:
            typer.echo("skipped (invalid band)")
            continue
        rationale = typer.prompt("rationale").strip() or "n/a"
        confidence = float(typer.prompt("confidence 0-1", default="0.7"))
        label = AnnotatorLabel(
            annotator=annotator,
            band=band,
            abstain=abstain,
            rationale=rationale,
            confidence=confidence,
            at=datetime.now(timezone.utc),
        )
        items.append(
            ItemLabels(
                candidate_id=cand.id,
                prompt=cand.prompt,
                category=cand.category,
                labels=[label],
            )
        )
    save_labels(out, items)
    typer.echo(f"Wrote {len(items)} labels to {out}.")


def _merge_label_files(paths: list[Path]) -> list[ItemLabels]:
    """Merge multiple annotators' JSONL label files by candidate id."""
    merged: dict[str, ItemLabels] = {}
    for p in paths:
        for item in load_labels(p):
            if item.candidate_id in merged:
                merged[item.candidate_id].labels.extend(item.labels)
            else:
                merged[item.candidate_id] = item.model_copy(deep=True)
    return list(merged.values())


@dataset_app.command("build")
def build(
    labels: list[Path] = typer.Option(..., "--labels", help="One JSONL label file per annotator."),
    out_dir: Path = typer.Option(..., "--out-dir", help="Directory for the built dataset."),
    version: str = typer.Option("v2.0.0", "--version"),
    adjudications: Path = typer.Option(None, "--adjudications", help="Optional tie-break JSON."),
):
    """Merge labels, adjudicate, split leakage-safely, and write a versioned dataset."""
    merged = _merge_label_files(labels)
    decisions = {}
    if adjudications and adjudications.exists():
        for row in json.loads(adjudications.read_text(encoding="utf-8")):
            decisions[row["candidate_id"]] = Adjudication(
                adjudicator=row["adjudicator"],
                band=ContextBand(row["band"]) if row.get("band") else None,
                abstain=bool(row.get("abstain", False)),
                rationale=row["rationale"],
                confidence=float(row.get("confidence", 0.6)),
            )

    resolved: list[AdjudicatedItem] = []
    unresolved: list[str] = []
    for item in merged:
        adj = decisions.get(item.candidate_id)
        out = resolve(item, adjudication=adj)
        if out is None:
            unresolved.append(item.candidate_id)
        else:
            resolved.append(out)

    if unresolved:
        typer.echo(
            f"{len(unresolved)} disagreed item(s) need adjudication: {', '.join(unresolved[:8])}"
            + ("..." if len(unresolved) > 8 else ""),
            err=True,
        )
        raise typer.Exit(2)

    frozen = _frozen_holdout_prompts()
    result = partition(resolved, frozen_holdout_prompts=frozen)

    out_dir.mkdir(parents=True, exist_ok=True)
    counts, shas = {}, {}
    for name, items in result.as_dict().items():
        path = out_dir / f"context_band_{name}_{version}.yaml"
        save_dataset(path, items)
        counts[name] = len(items)
        shas[name] = split_sha256(items)

    leak_report = out_dir / "leakage_report.json"
    leak_report.write_text(
        json.dumps(
            {
                "frozen_holdout_prompts_checked": len(frozen),
                "dev_leaks": len(find_leakage([i.prompt for i in result.dev], frozen)),
                "holdout_leaks": len(find_leakage([i.prompt for i in result.holdout], frozen)),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    banded = [i for items in result.as_dict().values() for i in items if not i.abstained]
    manifest = DatasetManifest(
        version=version,
        created=datetime.now(timezone.utc).date().isoformat(),
        split_counts=counts,
        split_sha256=shas,
        category_counts=_count(i.category for items in result.as_dict().values() for i in items),
        band_counts=_count(i.band.value for i in banded if i.band),
        leakage_report=str(leak_report.name),
        provenance="TASK-011 candidate-generated, human-review-pending; frozen holdout untouched.",
    )
    save_manifest(out_dir / f"manifest_{version}.json", manifest)
    typer.echo(f"Built dataset {version}: {counts}. Leakage report -> {leak_report}.")


def _count(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


@dataset_app.command("compare")
def compare(
    dev: Path = typer.Argument(..., help="A built dev dataset YAML."),
    out: Path = typer.Option(None, "--out", help="Optional JSON report path."),
    threshold: float = typer.Option(0.6, "--hybrid-threshold", min=0.0, max=1.0),
):
    """Compare rules/learned/hybrid on the new dev split (never the frozen holdout)."""
    items = load_dataset(dev)
    reports = compare_all(items, threshold=threshold)
    payload = {s: r.__dict__ for s, r in reports.items()}
    for s, r in reports.items():
        typer.echo(
            f"{s:7s} acc={r.accuracy} macroF1={r.macro_f1} "
            f"recall={r.per_band_recall} CI={r.acc_ci95} ECE={r.ece} "
            f"rules_fallback={r.rules_fallback_rate} abstained={r.abstained_items}"
        )
    if out:
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        typer.echo(f"Wrote comparison report to {out}.")


@dataset_app.command("leakage")
def leakage(dataset: Path = typer.Argument(..., help="Dataset YAML to check vs frozen holdout.")):
    """Report exact/near duplicates between a dataset and the frozen holdout."""
    items = load_dataset(dataset)
    frozen = _frozen_holdout_prompts()
    leaks = find_leakage([i.prompt for i in items], frozen)
    typer.echo(f"Checked {len(items)} items vs {len(frozen)} frozen prompts: {len(leaks)} leak(s).")
    for lk in leaks[:20]:
        typer.echo(f"  {lk.kind} {lk.score}: {lk.left!r} ~ {lk.right!r}")
    raise typer.Exit(1 if leaks else 0)
