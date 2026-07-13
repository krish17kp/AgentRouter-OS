"""AgentRouter OS CLI (Typer) — thin shell over the engine (CLI_SPEC.md).

Exit codes: 0 ok | 1 runtime error | 2 bad usage | 3 registry validation | 4 no eligible model.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import timezone
from importlib import resources
from pathlib import Path

import typer
import yaml

from . import store
from .classifier import classify
from .engine import BASE_WEIGHTS
from .engine import route as engine_route
from .learning import learned_weights
from .prompts import generate_prompt
from .refresh import (
    FETCHERS,
    GENERATED_SUFFIX,
    SUPPORTED_PROVIDERS,
    RefreshError,
    write_generated_registry,
)
from .registry import RegistryError, load_all_models, load_providers
from .safety import gates_for
from .schema import Classification, Level, PricingTier

app = typer.Typer(
    help="AgentRouter OS - route AI tasks to the best model/tool.", add_completion=False
)


def _version_callback(value: bool):
    if value:
        from importlib.metadata import PackageNotFoundError, version

        try:
            typer.echo(f"agentrouter-os {version('agentrouter-os')}")
        except PackageNotFoundError:
            typer.echo("agentrouter-os (not installed as a package)")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
):
    pass


registry_app = typer.Typer(help="Registry inspection.")
providers_app = typer.Typer(help="Provider operations.")
prompt_app = typer.Typer(help="Prompt generation.")
app.add_typer(registry_app, name="registry")
app.add_typer(providers_app, name="providers")
app.add_typer(prompt_app, name="prompt")

EXIT_RUNTIME, EXIT_USAGE, EXIT_REGISTRY, EXIT_NO_MODEL = 1, 2, 3, 4


def _home() -> Path:
    return Path(os.environ.get("AGENTROUTER_HOME", Path.home() / ".agentrouter"))


def _load_registries():
    home = _home()
    try:
        providers = load_providers(home / "registry" / "providers.yaml")
        models, warnings = load_all_models(home / "registry", providers)
    except RegistryError as e:
        typer.echo(f"Registry error: {e}", err=True)
        typer.echo("Why: routing needs a valid model registry to score against.", err=True)
        typer.echo(
            "Next: fix the file above, or re-seed defaults with: agentrouter init --force", err=True
        )
        raise typer.Exit(EXIT_REGISTRY) from e
    for w in warnings:
        typer.echo(f"warning: {w}", err=True)
    return providers, models


def _load_config() -> dict:
    cfg_path = _home() / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        typer.echo(f"Config error: invalid YAML in {cfg_path}: {e}", err=True)
        typer.echo("Why: scoring weights are read from this file.", err=True)
        typer.echo(
            "Next: fix the YAML, delete the file to use defaults, "
            "or re-seed with: agentrouter init --force",
            err=True,
        )
        raise typer.Exit(EXIT_REGISTRY) from e
    if not isinstance(cfg, dict):
        typer.echo(f"Config error: {cfg_path} must be a YAML mapping.", err=True)
        typer.echo(
            "Next: delete the file to use defaults, or re-seed with: agentrouter init --force",
            err=True,
        )
        raise typer.Exit(EXIT_REGISTRY)
    return cfg


def _load_weights(cfg: dict | None = None) -> dict:
    cfg = _load_config() if cfg is None else cfg
    w = cfg.get("weights") or {}
    valid = {k: v for k, v in w.items() if k in BASE_WEIGHTS and isinstance(v, (int, float))}
    return {**BASE_WEIGHTS, **valid}


def _apply_policy(models: list, cfg: dict) -> list:
    """M7 policy control: config `policy.max_pricing_tier` caps what routing may pick.

    With AGENTROUTER_HOME pointing at a shared directory, this enforces the cap
    team-wide from one config file.
    """
    policy = cfg.get("policy") or {}
    if not isinstance(policy, dict):
        typer.echo("Config error: 'policy' must be a mapping.", err=True)
        raise typer.Exit(EXIT_REGISTRY)
    max_tier = policy.get("max_pricing_tier")
    if max_tier is None:
        return models
    tiers = [t.value for t in PricingTier]
    if max_tier not in tiers:
        typer.echo(
            f"Config error: policy.max_pricing_tier '{max_tier}' is not one of {tiers}.", err=True
        )
        raise typer.Exit(EXIT_REGISTRY)
    cap = tiers.index(max_tier)
    kept = [m for m in models if tiers.index(m.pricing_tier.value) <= cap]
    dropped = len(models) - len(kept)
    if dropped:
        typer.echo(f"policy: excluded {dropped} model(s) above pricing tier '{max_tier}'", err=True)
    return kept


def _adapted_weights(cfg: dict) -> tuple[dict, str | None]:
    """Base/config weights, plus M4 feedback adaptation unless `learning: false`."""
    weights = _load_weights(cfg)
    if cfg.get("learning", True) is False:
        return weights, None
    conn = store.connect(_home())
    weights, note = learned_weights(conn, weights)
    conn.close()
    return weights, note


def _reason_for(rec: dict, cls, shifts: list[str]) -> str:
    """One-line plain-English justification for the recommendation."""
    t = rec["terms"]
    parts = [
        f"strongest weighted fit for {cls.task_type.value} "
        f"(capability {t['cap']}, cost-fit {t['cost']}, context-fit {t['ctx']})"
    ]
    if t["adj"] > 0:
        parts.append("ideal-use-case match")
    if cls.tool_needs:
        parts.append(f"supports required tools: {', '.join(cls.tool_needs)}")
    for s in shifts:
        if "high" in s:
            parts.append("capability weighted up (high complexity/risk)")
        elif "low" in s:
            parts.append("cost weighted up (simple task)")
        elif "large" in s:
            parts.append("context fit weighted up (large input)")
    return "; ".join(parts)


# --- init --------------------------------------------------------------------


@app.command()
def init(force: bool = typer.Option(False, "--force", help="Overwrite existing files.")):
    """Scaffold ~/.agentrouter/ with default config and seed registries."""
    home = _home()
    reg_dir = home / "registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    seeds = resources.files("agentrouter") / "seeds"
    targets = {
        "config.yaml": home / "config.yaml",
        "providers.yaml": reg_dir / "providers.yaml",
        "models.yaml": reg_dir / "models.yaml",
    }
    for name, dest in targets.items():
        if dest.exists() and not force:
            typer.echo(f"exists, skipped: {dest} (use --force to overwrite)")
            continue
        with resources.as_file(seeds / name) as src:
            shutil.copyfile(src, dest)
        typer.echo(f"Created {dest}")
    store.connect(home).close()
    typer.echo(f"Initialized {home / 'agentrouter.db'}")
    typer.echo('Ready. Try: agentrouter route "your task here"')


# --- route ---------------------------------------------------------------------


@app.command()
def route(
    task: str = typer.Argument(..., help="Free-text task description."),
    context_tokens: int | None = typer.Option(
        None, "--context-tokens", help="Override estimated context size."
    ),
    risk: Level | None = typer.Option(None, "--risk", help="Override inferred risk."),
    tool: str | None = typer.Option(None, "--tool", help="Override tool needs (comma-separated)."),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable output."),
    no_log: bool = typer.Option(False, "--no-log", help="Do not persist the decision."),
):
    """Classify a task and recommend the best model/tool + fallback."""
    _, models = _load_registries()
    cfg = _load_config()
    models = _apply_policy(models, cfg)
    tools = [t.strip() for t in tool.split(",") if t.strip()] if tool else None
    cls = classify(task, context_tokens=context_tokens, risk=risk, tools=tools)
    weights, learn_note = _adapted_weights(cfg)
    result = engine_route(models, cls, weights)
    if learn_note:
        result["weight_shifts"].append(learn_note)
    gates = gates_for(cls)

    rec = result["recommendation"]
    target = rec["model"] if rec else (result["manual_suggestion"] or "manual/human-operator")
    prompt = generate_prompt(task, target, cls, gates["checklist"])
    reason = _reason_for(rec, cls, result["weight_shifts"]) if rec else None

    payload = {
        "classification": cls.model_dump(mode="json"),
        **result,
        "reason": reason,
        "gates": gates,
        "prompt": prompt,
    }
    decision_id = None
    if not no_log:
        conn = store.connect(_home())
        decision_id = store.save_decision(conn, task, payload)
        conn.close()

    if json_out:
        typer.echo(json.dumps({"decision_id": decision_id, "task": task, **payload}, indent=2))
    else:
        _print_route(task, cls, result, gates, reason, decision_id)

    if rec is None:
        raise typer.Exit(EXIT_NO_MODEL)


def _print_route(task, cls, result, gates, reason, decision_id):
    typer.echo(f'\nTask: "{task}"')
    typer.echo("\nHow I read this task")
    typer.echo(
        f"  type: {cls.task_type.value:<14} complexity: {cls.complexity.value:<8}"
        f" risk: {cls.risk.value}"
    )
    typer.echo(
        f"  context: ~{cls.context_tokens} tokens ({cls.context_band.value})"
        f"    output: {cls.output_type.value}"
    )
    typer.echo(f"  tools needed: {', '.join(cls.tool_needs) or 'none'}")
    typer.echo(f"  approval: {cls.approval_level.value}")

    typer.echo("\nRecommendation                                        score")
    if result["recommendation"]:
        rec, fb = result["recommendation"], result["fallback"]
        typer.echo(f"  1  {rec['model']:<44} {rec['score']:.2f}   <- recommended")
        if fb:
            typer.echo(f"  2  {fb['model']:<44} {fb['score']:.2f}   <- fallback")
        if reason:
            typer.echo(f"\nWhy: {reason}.")
    else:
        typer.echo("  No eligible model for this task.")
        typer.echo(
            "  Why: every registry model was excluded by a hard filter"
            " (context size, required tools, or retirement)."
        )
        typer.echo(
            "  Next: relax --tool/--context-tokens overrides, or add a capable model to"
            " the registry (agentrouter registry list to see what is loaded)."
        )
        if result["manual_suggestion"]:
            typer.echo(f"  Suggestion: {result['manual_suggestion']} (do it yourself)")

    typer.echo(f"\nSafety checklist (risk={cls.risk.value})")
    for item in gates["checklist"]:
        typer.echo(f"  [ ] {item}")

    if decision_id:
        typer.echo(
            f"\nDecision logged: {decision_id}  (prompt saved with it; task text is stored locally)"
        )
        typer.echo(
            f"Next: agentrouter explain {decision_id}"
            f"   or   agentrouter prompt generate --from {decision_id} --out prompt.md"
        )


# --- explain ---------------------------------------------------------------------


@app.command()
def explain(
    decision_id: str = typer.Argument(..., help="Decision id, e.g. d_00042."),
    json_out: bool = typer.Option(False, "--json"),
):
    """Reconstruct a logged decision: classification, eligibility, score table."""
    db_path = _home() / "agentrouter.db"
    if not db_path.exists():
        typer.echo(f"No decision log found at {db_path}.", err=True)
        typer.echo("Why: nothing has been routed yet, so there is nothing to explain.", err=True)
        typer.echo(
            'Next: agentrouter init (if not done), then agentrouter route "<task>"', err=True
        )
        raise typer.Exit(EXIT_USAGE)
    conn = store.connect(_home())
    payload = store.load_decision(conn, decision_id)
    if payload is None:
        recent = store.recent_ids(conn)
        conn.close()
        typer.echo(f"No decision found with id '{decision_id}'.", err=True)
        typer.echo("Why: ids look like d_00001 and are printed by 'agentrouter route'.", err=True)
        if recent:
            typer.echo(f"Next: try a recent id: {', '.join(recent)}", err=True)
        else:
            typer.echo('Next: agentrouter route "<task>" to create a decision first.', err=True)
        raise typer.Exit(EXIT_USAGE)
    conn.close()
    if json_out:
        typer.echo(json.dumps(payload, indent=2))
        return

    c = payload["classification"]
    typer.echo(f'Task: "{payload["task"]}"')
    typer.echo(
        f"Classification: {c['task_type']}/{c['complexity']}/{c['risk']}/"
        f"{c['context_band']} | tools[{','.join(c['tool_needs'])}]"
    )
    n_total = len(payload["scores"]) + len(payload["excluded"])
    typer.echo(f"\nEligibility: {n_total} models -> {len(payload['scores'])} eligible")
    for ex in payload["excluded"]:
        typer.echo(f"  excluded {ex['model']}: {ex['reason']}")

    typer.echo("\nScores")
    typer.echo(f"  {'model':<42} {'cap':>5} {'cost':>5} {'lat':>5} {'ctx':>5} {'adj':>5}  score")
    for i, row in enumerate(payload["scores"]):
        t = row["terms"]
        mark = (
            "  <- recommended"
            if i == 0
            else (
                "  <- fallback"
                if payload["fallback"] and row["model"] == payload["fallback"]["model"]
                else ""
            )
        )
        typer.echo(
            f"  {row['model']:<42} {t['cap']:>5} {t['cost']:>5} {t['lat']:>5}"
            f" {t['ctx']:>5} {t['adj']:>5}  {row['score']:.3f}{mark}"
        )

    w = payload["weights"]
    typer.echo(f"\nWeights: cap {w['w_cap']} cost {w['w_cost']} lat {w['w_lat']} ctx {w['w_ctx']}")
    for s in payload["weight_shifts"]:
        typer.echo(f"  shift: {s}")
    g = payload["gates"]
    typer.echo(
        f"Gate: approval={g['approval_level']}, auto_execute_allowed={g['auto_execute_allowed']}"
    )


# --- feedback (M4 — feeds the bounded learning loop) ------------------------------


@app.command()
def feedback(
    decision_id: str,
    rating: int = typer.Option(..., "--rating", min=1, max=5),
    note: str = typer.Option("", "--note"),
):
    """Record outcome feedback for a decision. Ratings feed bounded weight adaptation."""
    conn = store.connect(_home())
    if store.load_decision(conn, decision_id) is None:
        recent = store.recent_ids(conn)
        conn.close()
        typer.echo(f"No decision found with id '{decision_id}'.", err=True)
        if recent:
            typer.echo(f"Next: try a recent id: {', '.join(recent)}", err=True)
        raise typer.Exit(EXIT_USAGE)
    from datetime import datetime

    conn.execute(
        "INSERT INTO feedback (decision_id, created_at, rating, note) VALUES (?, ?, ?, ?)",
        (int(decision_id.removeprefix("d_")), datetime.now(timezone.utc).isoformat(), rating, note),
    )
    conn.commit()
    conn.close()
    typer.echo(
        f"Recorded rating {rating} for {decision_id}. Low ratings (<=2) nudge future "
        "routing toward capability, within bounds; set learning: false in config.yaml to disable."
    )


# --- registry list ---------------------------------------------------------------


@registry_app.command("list")
def registry_list(
    provider: str | None = typer.Option(None, "--provider"),
    active_only: bool = typer.Option(False, "--active-only"),
    json_out: bool = typer.Option(False, "--json"),
):
    """Print loaded models with key attributes."""
    _, models = _load_registries()
    rows = [
        m
        for m in models
        if (provider is None or m.provider == provider)
        and (not active_only or m.deprecation_status.value == "active")
    ]
    if json_out:
        typer.echo(json.dumps([m.model_dump(mode="json") for m in rows], indent=2))
        return
    typer.echo(
        f"{'PROVIDER':<12} {'MODEL_ID':<28} {'CTX':>10} {'PRICE':<9} {'LAT':<7} {'C/R/W':<7} TOOLS"
    )
    for m in rows:
        crw = f"{m.ability.coding}/{m.ability.reasoning}/{m.ability.writing}"
        typer.echo(
            f"{m.provider:<12} {m.model_id:<28} {m.context_window:>10}"
            f" {m.pricing_tier.value:<9} {m.latency_tier.value:<7} {crw:<7}"
            f" {','.join(m.tool_support) or '-'}"
        )


# --- providers refresh (M2 openrouter, M3 openai) ----------------------------------


@providers_app.command("refresh")
def providers_refresh(
    provider: str = typer.Argument("openrouter", help="Provider to refresh."),
    limit: int = typer.Option(25, "--limit", min=1, help="Max models to import from the catalog."),
    match: str | None = typer.Option(
        None, "--match", help="Only import models whose id contains this substring."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be imported; write nothing."
    ),
):
    """Fetch a provider's live model catalog into a generated registry file.

    Writes registry/models.<provider>.generated.yaml. The manual models.yaml is
    never touched and always wins on collision; delete the generated file to revert.
    """
    if provider not in SUPPORTED_PROVIDERS:
        typer.echo(f"Provider '{provider}' is not refreshable in this build.", err=True)
        typer.echo(
            f"Why: only these adapters have live refresh: {', '.join(SUPPORTED_PROVIDERS)}.",
            err=True,
        )
        typer.echo(
            f"Next: agentrouter providers refresh {SUPPORTED_PROVIDERS[0]}, or edit "
            f"{_home() / 'registry' / 'models.yaml'} by hand.",
            err=True,
        )
        raise typer.Exit(EXIT_USAGE)

    reg_dir = _home() / "registry"
    if not reg_dir.is_dir():
        typer.echo(f"Registry directory not found: {reg_dir}", err=True)
        typer.echo("Why: refresh writes next to your manual registry.", err=True)
        typer.echo("Next: run agentrouter init first.", err=True)
        raise typer.Exit(EXIT_REGISTRY)

    fetcher, key_env = FETCHERS[provider]
    api_key = os.environ.get(key_env)  # header-only; never echoed/logged
    typer.echo(
        f"auth: using {key_env} from environment"
        if api_key
        else f"auth: no {key_env} set"
        + (" - using the public catalog endpoint" if provider == "openrouter" else "")
    )
    try:
        entries, warnings = fetcher(api_key, limit, match)
    except RefreshError as e:
        typer.echo(f"Refresh failed: {e}", err=True)
        typer.echo(
            "Why: the live catalog could not be fetched or parsed; your registry was NOT modified.",
            err=True,
        )
        typer.echo(
            "Next: check your network, retry later, or keep using the manual "
            "registry (models.yaml) - routing works without refresh.",
            err=True,
        )
        raise typer.Exit(EXIT_RUNTIME) from e
    for w in warnings:
        typer.echo(f"warning: {w}", err=True)

    typer.echo(f"Fetched {len(entries)} models from {provider}:")
    for e in entries:
        typer.echo(f"  {e.key:<52} ctx {e.context_window:>9}  {e.pricing_tier.value}")
    if dry_run:
        typer.echo("\nDry run - nothing written.")
        return
    path = write_generated_registry(reg_dir, provider, entries)
    typer.echo(f"\nWrote {path}")
    typer.echo(
        "Manual models.yaml is untouched and wins on collision. "
        f"Delete the {GENERATED_SUFFIX} file to revert."
    )
    typer.echo("Next: agentrouter registry list")


# --- prompt generate ---------------------------------------------------------------


@prompt_app.command("generate")
def prompt_generate(
    task: str | None = typer.Argument(None, help="Task text (or use --from)."),
    from_id: str | None = typer.Option(None, "--from", help="Regenerate from a decision id."),
    tool: str | None = typer.Option(None, "--tool", help="Target tool key (provider/model_id)."),
    out: Path | None = typer.Option(None, "--out", help="Write prompt to a file."),
):
    """Generate an execution prompt for a task or a logged decision."""
    if from_id:
        conn = store.connect(_home())
        payload = store.load_decision(conn, from_id)
        recent = store.recent_ids(conn)
        conn.close()
        if payload is None:
            typer.echo(f"No decision found with id '{from_id}'.", err=True)
            typer.echo(
                "Why: ids look like d_00001 and are printed by 'agentrouter route'.", err=True
            )
            if recent:
                typer.echo(f"Next: try a recent id: {', '.join(recent)}", err=True)
            else:
                typer.echo('Next: agentrouter route "<task>" to create a decision first.', err=True)
            raise typer.Exit(EXIT_USAGE)
        prompt = payload["prompt"]
        target = tool or (
            payload["recommendation"]["model"]
            if payload["recommendation"]
            else "manual/human-operator"
        )
        if tool:  # regenerate for a different tool
            cls = Classification(**payload["classification"])
            prompt = generate_prompt(payload["task"], tool, cls, payload["gates"]["checklist"])
    elif task:
        _, models = _load_registries()
        cls = classify(task)
        gates = gates_for(cls)
        if tool:
            target = tool
        else:
            result = engine_route(models, cls, _load_weights())
            rec = result["recommendation"]
            target = (
                rec["model"] if rec else (result["manual_suggestion"] or "manual/human-operator")
            )
        prompt = generate_prompt(task, target, cls, gates["checklist"])
    else:
        typer.echo("Provide a task or --from <decision_id>.", err=True)
        raise typer.Exit(EXIT_USAGE)

    if out:
        out.write_text(prompt, encoding="utf-8")
        typer.echo(f"Wrote execution prompt for {target} -> {out}")
    else:
        typer.echo(prompt)


# --- execute (M6 — opt-in, hard safety gate) ---------------------------------------


@app.command()
def execute(
    decision_id: str = typer.Argument(..., help="Decision id to execute, e.g. d_00042."),
    yes: bool = typer.Option(False, "--yes", help="Confirm running the recommended tool."),
):
    """Run the recommended tool for a logged decision (opt-in; high risk never executes).

    Requires the recommendation's provider to have supports_execution: true and an
    exec_command in providers.yaml — both ship disabled by default.
    """
    conn = store.connect(_home())
    payload = store.load_decision(conn, decision_id)
    recent = store.recent_ids(conn)
    conn.close()
    if payload is None:
        typer.echo(f"No decision found with id '{decision_id}'.", err=True)
        if recent:
            typer.echo(f"Next: try a recent id: {', '.join(recent)}", err=True)
        raise typer.Exit(EXIT_USAGE)

    gates = payload["gates"]
    if not gates["auto_execute_allowed"]:
        typer.echo(f"Execution blocked for {decision_id}.", err=True)
        typer.echo(
            f"Why: risk={payload['classification']['risk']}, "
            f"approval={gates['approval_level']} - this decision requires a human to run "
            "the task themselves (NFR-8: high risk never auto-executes).",
            err=True,
        )
        typer.echo(
            f"Next: agentrouter prompt generate --from {decision_id} --out prompt.md "
            "and run the tool yourself.",
            err=True,
        )
        raise typer.Exit(EXIT_USAGE)

    rec = payload["recommendation"]
    if rec is None:
        typer.echo("Nothing to execute: this decision had no eligible model.", err=True)
        raise typer.Exit(EXIT_USAGE)
    providers, _ = _load_registries()
    provider = providers.get(rec["provider"])
    if provider is None or not provider.supports_execution or not provider.exec_command:
        typer.echo(f"Execution is not enabled for provider '{rec['provider']}'.", err=True)
        typer.echo(
            "Why: execution is opt-in per provider; it needs supports_execution: true "
            "AND an exec_command in registry/providers.yaml.",
            err=True,
        )
        typer.echo(
            f"Next: edit {_home() / 'registry' / 'providers.yaml'} to opt in, or run the "
            "generated prompt yourself.",
            err=True,
        )
        raise typer.Exit(EXIT_USAGE)

    argv = [a.replace("{prompt}", payload["prompt"]) for a in provider.exec_command]
    if not yes:
        typer.echo(f"Would run (provider {provider.id}): {provider.exec_command}")
        typer.echo("Next: re-run with --yes to execute.")
        raise typer.Exit(EXIT_USAGE)

    import subprocess

    typer.echo(f"Running {rec['model']} via provider '{provider.id}'...")
    try:
        completed = subprocess.run(argv)  # no shell; prompt passed as one argv element
    except FileNotFoundError as e:
        typer.echo(f"Execution failed: command not found: {argv[0]}", err=True)
        typer.echo("Next: install the provider's CLI or fix exec_command.", err=True)
        raise typer.Exit(EXIT_RUNTIME) from e
    raise typer.Exit(completed.returncode)


# --- stats (M7 telemetry — local aggregates) ----------------------------------------


@app.command()
def stats(json_out: bool = typer.Option(False, "--json")):
    """Aggregate telemetry from the local decision log: counts, tiers, feedback."""
    db_path = _home() / "agentrouter.db"
    if not db_path.exists():
        typer.echo(f"No decision log found at {db_path}.", err=True)
        typer.echo('Next: agentrouter init, then agentrouter route "<task>"', err=True)
        raise typer.Exit(EXIT_USAGE)
    _, models = _load_registries()
    tier_by_key = {m.key: m.pricing_tier.value for m in models}
    conn = store.connect(_home())
    agg = store.aggregate_stats(conn, tier_by_key)
    conn.close()
    if json_out:
        typer.echo(json.dumps(agg, indent=2))
        return
    typer.echo(f"Decisions logged: {agg['decisions']}")
    typer.echo(
        "By risk: " + (", ".join(f"{k}={v}" for k, v in sorted(agg["by_risk"].items())) or "-")
    )
    typer.echo(
        "By recommended pricing tier: "
        + (", ".join(f"{k}={v}" for k, v in sorted(agg["by_pricing_tier"].items())) or "-")
    )
    typer.echo(
        "By user: " + (", ".join(f"{k}={v}" for k, v in sorted(agg["by_user"].items())) or "-")
    )
    fb = agg["feedback"]
    avg = fb["avg_rating"] if fb["avg_rating"] is not None else "-"
    acc = fb["acceptance_rate"] if fb["acceptance_rate"] is not None else "-"
    typer.echo(f"Feedback: {fb['count']} rating(s), avg {avg}, acceptance rate {acc}")


# --- dashboard (M5 — read-only, stdlib) ----------------------------------------------


@app.command()
def dashboard(port: int = typer.Option(8321, "--port", min=0, max=65535)):
    """Serve a read-only local dashboard over the decision log (Ctrl+C to stop)."""
    from .dashboard import serve

    db_path = _home() / "agentrouter.db"
    if not db_path.exists():
        typer.echo(f"No decision log found at {db_path}.", err=True)
        typer.echo('Next: agentrouter init, then agentrouter route "<task>"', err=True)
        raise typer.Exit(EXIT_USAGE)
    _, models = _load_registries()
    serve(_home(), port, {m.key: m.pricing_tier.value for m in models})


# --- evaluate (graded classifier benchmark) ------------------------------------------

_DEFAULT_GOLD = Path("benchmarks") / "classifier_gold_v1.yaml"
_DEFAULT_ARTIFACTS = Path("artifacts")


@app.command()
def evaluate(
    gold: Path = typer.Option(_DEFAULT_GOLD, "--gold", help="Gold benchmark YAML."),
    out_dir: Path = typer.Option(_DEFAULT_ARTIFACTS, "--out-dir", help="Where to write artifacts."),
    json_out: bool = typer.Option(False, "--json", help="Print the full report as JSON."),
    no_artifacts: bool = typer.Option(False, "--no-artifacts", help="Do not write files."),
):
    """Grade the classifier against a gold benchmark; write evaluation artifacts."""
    from . import evaluate as ev

    try:
        report = ev.evaluate(gold)
    except ev.GoldError as e:
        typer.echo(f"Benchmark error: {e}", err=True)
        raise typer.Exit(EXIT_REGISTRY) from e

    if not no_artifacts:
        paths = ev.write_artifacts(report, out_dir)
        for p in paths:
            typer.echo(f"Wrote {p}")

    if json_out:
        slim = {k: v for k, v in report.items() if k != "cases"}
        typer.echo(json.dumps(slim, indent=2))
        return

    typer.echo(f"\nCases: {report['n_cases']}   Overall grade: {report['overall_grade']}/100")
    typer.echo(f"Release-ready: {'YES' if report['release_ready'] else 'NO'}")
    typer.echo("\nDimension scores (weight x score):")
    for d, w in report["grade_weights"].items():
        typer.echo(f"  {d:<11} w={w:<2} score={report['dimension_scores'][d]:.3f}")
    typer.echo(
        f"\nTask-type macro F1: {report['task_type']['macro_f1']:.3f}   "
        f"high-risk recall: {report['risk']['high_risk_recall']}   "
        f"tool F1: {report['tools']['f1']:.3f}   "
        f"approval acc: {report['approval']['accuracy']:.3f}"
    )
    typer.echo("\nRelease thresholds:")
    for name, ok in report["release_thresholds"].items():
        typer.echo(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    typer.echo(f"\nFailed cases: {len(report['failures'])} (see artifacts/failures.csv)")


if __name__ == "__main__":
    app()
