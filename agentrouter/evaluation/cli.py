"""`agentrouter evaluate ...` sub-app (program §1 CLI experience).

Thin Typer shell over runner/registry/reports/comparison. Understandable
without reading source: list-datasets, validate-dataset, run, report, compare.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import comparison, reports, runner
from .base import AdapterError, SkippedExternal
from .registry import PROFILES, dataset_names, get_adapter, try_get_adapter

eval_app = typer.Typer(help="Graded evaluation against gold + public benchmarks.")

_DEFAULT_OUT = Path("artifacts") / "evaluation"


@eval_app.command("list-datasets")
def list_datasets():
    """Show every registered dataset and its availability."""
    for name in dataset_names():
        adapter = try_get_adapter(name)
        if adapter is None:
            typer.echo(f"{name:<16} {'unavailable':<16} (adapter not importable)")
            continue
        d = adapter.describe()
        typer.echo(f"{name:<16} {d['availability']:<16} license={d['license']}")


@eval_app.command("validate-dataset")
def validate_dataset(path: str = typer.Argument(..., help="Dataset name or gold YAML path.")):
    """Load + validate a dataset (or a gold YAML by path); report case count."""
    try:
        if path in dataset_names():
            cases = get_adapter(path).load()
        else:
            from .adapters.agentrouter_gold import AgentRouterGoldAdapter

            cases = AgentRouterGoldAdapter(Path(path)).load()
    except (AdapterError, FileNotFoundError, KeyError) as e:
        typer.echo(f"Invalid dataset: {e}", err=True)
        raise typer.Exit(3) from e
    typer.echo(f"OK: {len(cases)} cases validated.")


@eval_app.command("run")
def run_cmd(
    profile: str = typer.Option("fast", "--profile", help=f"One of: {', '.join(PROFILES)}"),
    dataset: str | None = typer.Option(None, "--dataset", help="Single dataset name."),
    limit: int | None = typer.Option(None, "--limit", help="Cap cases (deterministic sample)."),
    seed: int = typer.Option(0, "--seed", help="Sampling seed."),
    languages: str | None = typer.Option(None, "--languages", help="Comma list, e.g. en,hi."),
    source: str = typer.Option(
        "fixture", "--source", help="fixture | real (real never falls back)."
    ),
    out_dir: Path = typer.Option(_DEFAULT_OUT, "--out-dir", help="Artifact directory."),
    json_out: bool = typer.Option(False, "--json", help="Print full result JSON."),
    no_artifacts: bool = typer.Option(False, "--no-artifacts", help="Do not write files."),
    measure_all: bool = typer.Option(
        False, "--all", help="Measure every 100-point dimension (routing/safety/platform/...)."
    ),
):
    """Run an evaluation profile or a single dataset and write reports."""
    if source not in ("fixture", "real"):
        typer.echo(f"Invalid --source '{source}' (use fixture|real).", err=True)
        raise typer.Exit(2)
    langs = [x.strip() for x in languages.split(",")] if languages else None
    try:
        result = runner.run(
            profile=None if dataset else profile,
            dataset=dataset,
            limit=limit,
            seed=seed,
            languages=langs,
            source=source,
            measure_all=measure_all,
        )
    except (KeyError, AdapterError) as e:
        typer.echo(f"Run error: {e}", err=True)
        raise typer.Exit(3) from e

    if not no_artifacts:
        for p in reports.write_reports(result, out_dir):
            typer.echo(f"Wrote {p}")

    if json_out:
        typer.echo(json.dumps({k: v for k, v in result.items() if k != "classification"}, indent=2))
        return

    typer.echo(
        f"\nGrade /100: {result['grade_over_100']}  (measured: {result['grade_of_measured']})"
    )
    typer.echo(f"Release-ready: {'YES' if result['release_ready'] else 'NO'}")
    typer.echo(f"Cases: {result['n_cases']}")
    typer.echo("\nDatasets:")
    for name, info in result["datasets"].items():
        typer.echo(f"  {name:<16} {info['status']:<16} n={info['n']}")
    typer.echo("\nRelease gates:")
    for name, ok in result["release_gates"].items():
        typer.echo(f"  [{'PASS' if ok else 'FAIL'}] {name}")


@eval_app.command("report")
def report_cmd(result_json: Path = typer.Argument(..., help="Path to a result.json.")):
    """Render a Markdown report from an existing result.json to stdout."""
    if not result_json.exists():
        typer.echo(f"Not found: {result_json}", err=True)
        raise typer.Exit(3)
    result = json.loads(result_json.read_text(encoding="utf-8"))
    typer.echo(reports.render_markdown(result))


@eval_app.command("compare")
def compare_cmd(
    baseline: Path = typer.Argument(..., help="Baseline result.json."),
    current: Path = typer.Argument(..., help="Current result.json."),
    out_dir: Path = typer.Option(_DEFAULT_OUT, "--out-dir"),
):
    """Compare two result.json files; write comparison artifacts."""
    for p in (baseline, current):
        if not p.exists():
            typer.echo(f"Not found: {p}", err=True)
            raise typer.Exit(3)
    cmp = comparison.compare(comparison.load_result(baseline), comparison.load_result(current))
    for p in comparison.write_comparison(cmp, out_dir):
        typer.echo(f"Wrote {p}")
    typer.echo(f"\nGrade delta: {cmp['grade_delta']}")
    typer.echo(f"Critical regression: {'YES' if cmp['has_critical_regression'] else 'NO'}")
    if cmp["has_critical_regression"]:
        raise typer.Exit(1)


@eval_app.command("prepare")
def prepare_cmd(
    dataset: str | None = typer.Option(None, "--dataset", help="Dataset to prepare."),
    all_: bool = typer.Option(False, "--all", help="Prepare every registered dataset."),
    limit: int | None = typer.Option(None, "--limit", help="Cap records for a smoke prepare."),
):
    """Download + normalize the REAL dataset(s) into the HF cache. Reports provenance.

    Never falls back to fixtures: an unavailable dataset is reported SKIPPED_EXTERNAL
    with the exact blocker. Set HF_HOME to control the cache location.
    """
    if not dataset and not all_:
        typer.echo("Specify --dataset <name> or --all.", err=True)
        raise typer.Exit(2)
    names = dataset_names() if all_ else [dataset]
    any_ok = False
    for name in names:
        adapter = try_get_adapter(name)
        if adapter is None:
            typer.echo(f"{name:<16} UNAVAILABLE (adapter not importable)")
            continue
        try:
            rep = adapter.prepare(limit=limit)
            any_ok = True
            typer.echo(
                f"{name:<16} REAL   records={rep['downloaded_records']} "
                f"repo={rep.get('hf_repo')} license={rep['license']}"
            )
        except SkippedExternal as e:
            typer.echo(f"{name:<16} SKIPPED_EXTERNAL  {e}")
        except AdapterError as e:
            typer.echo(f"{name:<16} ERROR  {e}")
    if not any_ok and not all_:
        raise typer.Exit(1)


@eval_app.command("status")
def status_cmd():
    """Show each dataset's fixture + real availability and remaining blocker."""
    typer.echo(f"{'dataset':<16} {'fixture':<9} {'real':<6} blocker/notes")
    for name in dataset_names():
        adapter = try_get_adapter(name)
        if adapter is None:
            typer.echo(f"{name:<16} {'n/a':<9} {'n/a':<6} adapter not importable")
            continue
        d = adapter.describe()
        fixture = (
            "yes" if d["availability"] == "fixture_only" or d["availability"] == "ready" else "no"
        )
        real = "yes" if d["real_available"] else "no"
        note = "" if d["real_available"] else d["real_reason"]
        typer.echo(f"{name:<16} {fixture:<9} {real:<6} {note}")
