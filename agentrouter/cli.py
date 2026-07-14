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

from . import hosts, plugins, store
from .classifier import classify
from .controls import PREFERENCE_WEIGHTS, RouteControls, apply_controls
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
hosts_app = typer.Typer(help="Execution host discovery.")
models_app = typer.Typer(help="Model catalog inspection.")
plugin_app = typer.Typer(help="Install AgentRouter host integrations (skill/plugin).")
app.add_typer(registry_app, name="registry")
app.add_typer(providers_app, name="providers")
app.add_typer(prompt_app, name="prompt")
app.add_typer(hosts_app, name="hosts")
app.add_typer(models_app, name="models")
app.add_typer(plugin_app, name="plugin")

# Multi-dataset evaluation framework (evaluation/ package). The legacy
# single-shot `evaluate` command below is kept for backward compatibility.
from .evaluation.cli import eval_app  # noqa: E402

app.add_typer(eval_app, name="eval")

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


def _resolve_preference(quality: bool, balanced: bool, cheap: bool, fast: bool) -> str | None:
    """Map the four --prefer-* flags to a single preference name; at most one."""
    chosen = [
        n
        for n, on in (
            ("quality", quality),
            ("balanced", balanced),
            ("cheap", cheap),
            ("fast", fast),
        )
        if on
    ]
    if len(chosen) > 1:
        typer.echo(f"Use only one --prefer-* flag (got {', '.join(chosen)}).", err=True)
        raise typer.Exit(EXIT_USAGE)
    return chosen[0] if chosen else None


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


def _execution_route(row: dict | None, models_by_key: dict) -> dict | None:
    """Stage-2: resolve HOW to run the selected model (program Phase 5/6).

    Returns a JSON-serializable execution-route block, or None if the model has
    no execution targets (e.g. a refreshed catalog entry without host wiring).
    """
    if row is None:
        return None
    model = models_by_key.get(row["model"])
    if model is None or not model.execution_targets:
        return None
    resolved = hosts.resolve_execution_route(model, include_unavailable=True)
    tgt, status = resolved.target, resolved.status
    return {
        "vendor": model.vendor,
        "model_id": model.model_id,
        "display_name": model.name,
        "release_channel": model.release_channel.value,
        "host": tgt.host if tgt else None,
        "host_model_id": tgt.host_model_id if tgt else None,
        "execution_mode": tgt.execution_mode.value if tgt else None,
        "availability": status.availability if status else "unknown",
        "availability_reason": status.reason if status else "no execution target",
        "command_preview": hosts.command_preview(tgt) if tgt else None,
        "required_env": tgt.required_env if tgt else [],
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "all_hosts": [
            {"host": s.host, "availability": s.availability} for s in resolved.all_statuses
        ],
    }


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


def _write_preference(preference: str) -> None:
    """Persist a cost/quality preference as scoring weights in config.yaml."""
    cfg = _load_config()
    cfg["weights"] = dict(PREFERENCE_WEIGHTS[preference])
    (_home() / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


@app.command()
def setup(
    preference: str = typer.Option(
        "balanced", "--preference", help="quality | balanced | cheap | fast."
    ),
    sample: str = typer.Option(
        "summarize this PDF and list the action items", "--sample", help="First sample task."
    ),
):
    """Guided onboarding: init home, discover hosts, set a preference, run a sample route.

    Non-interactive and idempotent — safe to re-run and to run in CI.
    """
    if preference not in PREFERENCE_WEIGHTS:
        typer.echo(
            f"Unknown --preference '{preference}'. Choose: {', '.join(PREFERENCE_WEIGHTS)}.",
            err=True,
        )
        raise typer.Exit(EXIT_USAGE)

    typer.echo("AgentRouter setup - everything runs locally; no task text leaves this machine.\n")

    typer.echo("1. Home directory")
    init(force=False)

    typer.echo("\n2. Execution hosts (credentials detected by presence only; values never read)")
    available = 0
    for host in hosts.known_hosts():
        st = hosts.detect_host(host)
        mark = "OK " if st.availability == hosts.AVAILABLE else "-- "
        typer.echo(f"   [{mark}] {host:<16} {st.availability:<12} {st.reason}")
        available += st.availability == hosts.AVAILABLE
    if not available:
        typer.echo("   Note: no host available yet — install Claude Code/Codex or set an API key.")

    typer.echo(f"\n3. Preference: {preference}")
    _write_preference(preference)
    typer.echo(f"   Saved scoring weights to {_home() / 'config.yaml'}")

    typer.echo(f'\n4. Sample route: "{sample}"')
    _, models = _load_registries()
    cfg = _load_config()
    models = _apply_policy(models, cfg)
    cls = classify(sample)
    result = engine_route(models, cls, _load_weights(cfg))
    rec = result["recommendation"]
    if rec:
        typer.echo(f"   -> {rec['model']}  (score {rec['score']:.2f})")
    else:
        typer.echo("   -> no eligible model (check your registry)")

    typer.echo("\n5. Install a host integration:")
    typer.echo("   agentrouter plugin install claude-code    # or: codex")
    typer.echo('\nDone. Next: agentrouter route "<your task>"')


# --- route ---------------------------------------------------------------------


@app.command()
def route(
    task: str = typer.Argument(..., help="Free-text task description."),
    context_tokens: int | None = typer.Option(
        None, "--context-tokens", help="Override estimated context size."
    ),
    risk: Level | None = typer.Option(None, "--risk", help="Override inferred risk."),
    tool: str | None = typer.Option(None, "--tool", help="Override tool needs (comma-separated)."),
    uncertainty_threshold: float = typer.Option(
        0.4, "--uncertainty-threshold", help="Below this confidence, route flags clarification."
    ),
    vendor: list[str] = typer.Option(None, "--vendor", help="Only these vendors (repeatable)."),
    exclude_vendor: list[str] = typer.Option(
        None, "--exclude-vendor", help="Drop these vendors (repeatable)."
    ),
    model: str | None = typer.Option(None, "--model", help="Pin to one model (vendor/id or id)."),
    host: list[str] = typer.Option(
        None, "--host", help="Only models runnable on these hosts (repeatable)."
    ),
    exclude_host: list[str] = typer.Option(
        None, "--exclude-host", help="Drop models on these hosts (repeatable)."
    ),
    max_price: float | None = typer.Option(
        None, "--max-price", help="Cap input price (USD per 1M tokens)."
    ),
    prefer_quality: bool = typer.Option(False, "--prefer-quality", help="Weight capability."),
    prefer_balanced: bool = typer.Option(False, "--prefer-balanced", help="Balanced weights."),
    prefer_cheap: bool = typer.Option(False, "--prefer-cheap", help="Weight cost."),
    prefer_fast: bool = typer.Option(False, "--prefer-fast", help="Weight latency."),
    stable_only: bool = typer.Option(False, "--stable-only", help="Only stable-channel models."),
    allow_preview: bool = typer.Option(
        False, "--allow-preview", help="Include preview/experimental models (default)."
    ),
    available_only: bool = typer.Option(
        False, "--available-only", help="Only models with an available host."
    ),
    include_unavailable: bool = typer.Option(
        False, "--include-unavailable", help="Include models without an available host (default)."
    ),
    prohibit_tool: list[str] = typer.Option(
        None, "--prohibit-tool", help="Drop models supporting this tool (repeatable)."
    ),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable output."),
    no_log: bool = typer.Option(False, "--no-log", help="Do not persist the decision."),
):
    """Classify a task and recommend the best model/tool + fallback."""
    prefer = _resolve_preference(prefer_quality, prefer_balanced, prefer_cheap, prefer_fast)
    if stable_only and allow_preview:
        typer.echo("Use only one of --stable-only / --allow-preview.", err=True)
        raise typer.Exit(EXIT_USAGE)
    if available_only and include_unavailable:
        typer.echo("Use only one of --available-only / --include-unavailable.", err=True)
        raise typer.Exit(EXIT_USAGE)
    ctrl = RouteControls(
        vendor=tuple(vendor or ()),
        exclude_vendor=tuple(exclude_vendor or ()),
        model=model,
        host=tuple(host or ()),
        exclude_host=tuple(exclude_host or ()),
        max_price=max_price,
        stable_only=stable_only,
        available_only=available_only,
        prohibit_tool=tuple(prohibit_tool or ()),
    )

    _, models = _load_registries()
    cfg = _load_config()
    models = _apply_policy(models, cfg)
    models, control_drops = apply_controls(models, ctrl)
    tools = [t.strip() for t in tool.split(",") if t.strip()] if tool else None
    cls = classify(
        task,
        context_tokens=context_tokens,
        risk=risk,
        tools=tools,
        uncertainty_threshold=uncertainty_threshold,
    )
    weights, learn_note = _adapted_weights(cfg)
    result = engine_route(models, cls, weights, prefer=prefer)
    result["excluded"] = control_drops + result["excluded"]
    if learn_note:
        result["weight_shifts"].append(learn_note)
    gates = gates_for(cls)

    rec = result["recommendation"]
    target = rec["model"] if rec else (result["manual_suggestion"] or "manual/human-operator")
    prompt = generate_prompt(task, target, cls, gates["checklist"])
    reason = _reason_for(rec, cls, result["weight_shifts"]) if rec else None

    models_by_key = {m.key: m for m in models}
    exec_route = _execution_route(rec, models_by_key) if rec else None
    fb_route = _execution_route(result["fallback"], models_by_key) if result["fallback"] else None

    payload = {
        "classification": cls.model_dump(mode="json"),
        **result,
        "reason": reason,
        "gates": gates,
        "prompt": prompt,
        "execution_route": exec_route,
        "fallback_execution_route": fb_route,
    }
    decision_id = None
    if not no_log:
        conn = store.connect(_home())
        decision_id = store.save_decision(conn, task, payload)
        conn.close()

    if json_out:
        typer.echo(json.dumps({"decision_id": decision_id, "task": task, **payload}, indent=2))
    else:
        _print_route(task, cls, result, gates, reason, decision_id, exec_route, fb_route)

    if rec is None:
        raise typer.Exit(EXIT_NO_MODEL)


def _print_exec_block(label: str, er: dict | None):
    if not er:
        return
    typer.echo(f"\n{label}")
    typer.echo(f"  Model:          {er['display_name']}")
    typer.echo(f"  Vendor:         {er['vendor']}")
    typer.echo(f"  Model ID:       {er['model_id']}")
    typer.echo(f"  Run through:    {er['host'] or '(no host)'}")
    if er.get("host_model_id"):
        typer.echo(f"  Host model ID:  {er['host_model_id']}")
    typer.echo(f"  Availability:   {er['availability']}")
    typer.echo(f"  Release:        {er['release_channel']}")
    typer.echo(f"  Context:        {er['context_window']:,} tokens")
    if er.get("command_preview"):
        typer.echo(f"  Command:        {er['command_preview']}")
    if er["availability"] != hosts.AVAILABLE:
        typer.echo(f"  Note:           {er['availability_reason']}")


def _print_route(task, cls, result, gates, reason, decision_id, exec_route=None, fb_route=None):
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
    typer.echo(f"  confidence: {cls.confidence:.2f}")
    if cls.needs_clarification:
        alt = (
            f" (could also be {cls.alternative_task_type.value})"
            if cls.alternative_task_type
            else ""
        )
        why = f" — {cls.ambiguity_reason}" if cls.ambiguity_reason else ""
        typer.echo(f"\nLow confidence{why}{alt}.")
        typer.echo("  Consider clarifying the task; the recommendation below is a best guess.")

    typer.echo("\nRecommendation                                        score")
    if result["recommendation"]:
        rec, fb = result["recommendation"], result["fallback"]
        typer.echo(f"  1  {rec['model']:<44} {rec['score']:.2f}   <- recommended")
        if fb:
            typer.echo(f"  2  {fb['model']:<44} {fb['score']:.2f}   <- fallback")
        _print_exec_block("Recommendation", exec_route)
        _print_exec_block("Fallback", fb_route)
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


def _execute_via_host(rec: dict, er: dict, prompt: str, *, yes: bool, dry_run: bool):
    """Run the exact model on its resolved host (argv, shell=False). Phase 7."""
    _, models = _load_registries()
    model = next((m for m in models if m.key == rec["model"]), None)
    if model is None:
        typer.echo(f"Model '{rec['model']}' is no longer in the registry.", err=True)
        raise typer.Exit(EXIT_USAGE)
    resolved = hosts.resolve_execution_route(model, include_unavailable=True)
    tgt, status = resolved.target, resolved.status
    if tgt is None or status is None:
        typer.echo(f"No execution target for {model.key}.", err=True)
        raise typer.Exit(EXIT_USAGE)

    typer.echo(f"Model:       {model.name} ({model.vendor}/{model.model_id})")
    typer.echo(f"Run through: {tgt.host} (host model id {tgt.host_model_id})")
    typer.echo(f"Availability: {status.availability} ({status.reason})")
    if tgt.command_template:
        typer.echo(f"Command:     {hosts.command_preview(tgt)}")

    # --dry-run previews safely and NEVER executes, regardless of availability.
    if dry_run:
        typer.echo("Dry run: nothing executed.")
        raise typer.Exit(0)

    if not tgt.command_template:
        typer.echo(
            f"'{tgt.host}' is a {tgt.execution_mode.value} host with no local command; "
            "use the vendor API/SDK with the generated prompt."
        )
        raise typer.Exit(0)
    # never execute when availability is not confirmed (program Phase 7)
    if status.availability != hosts.AVAILABLE:
        typer.echo(f"Not enabled: host '{tgt.host}' is {status.availability}.", err=True)
        typer.echo(
            "Next: install/authenticate the host, or run the generated prompt yourself.", err=True
        )
        raise typer.Exit(EXIT_USAGE)
    if not yes:
        typer.echo("Next: re-run with --yes to execute (or --dry-run to preview).")
        raise typer.Exit(EXIT_USAGE)

    argv = [a.replace("{prompt}", prompt) for a in tgt.command_template]  # shell=False, one argv

    import subprocess

    typer.echo(f"Running {model.name} via {tgt.host}...")
    try:
        completed = subprocess.run(argv)  # nosec B603 - argv list, shell=False, no string interpolation (test_execute_injection.py)
    except FileNotFoundError as e:
        typer.echo(f"Execution failed: command not found: {argv[0]}", err=True)
        typer.echo(f"Next: install the '{tgt.host}' CLI ({tgt.required_command}).", err=True)
        raise typer.Exit(EXIT_RUNTIME) from e
    raise typer.Exit(completed.returncode)


# --- hosts (execution host discovery — Phase 4) --------------------------------------


@hosts_app.command("list")
def hosts_list():
    """List known execution hosts and whether they are available locally."""
    _, models = _load_registries()
    seen: dict[str, hosts.HostStatus] = {}
    for m in models:
        for t in m.execution_targets:
            if t.host not in seen:
                seen[t.host] = hosts.target_status(t)
    for host in hosts.known_hosts():
        if host not in seen:
            seen[host] = hosts.detect_host(host)
    for host, st in seen.items():
        typer.echo(f"{host:<16} {st.availability:<12} {st.reason}")


@hosts_app.command("doctor")
def hosts_doctor():
    """Diagnose host availability; exit non-zero if no host is available."""
    any_available = False
    for host in hosts.known_hosts():
        st = hosts.detect_host(host)
        mark = "OK " if st.availability == hosts.AVAILABLE else "-- "
        typer.echo(f"[{mark}] {host:<16} {st.availability:<12} {st.reason}")
        any_available = any_available or st.availability == hosts.AVAILABLE
    if not any_available:
        typer.echo(
            "\nNo execution host is available. Install Claude Code or Codex, or set an API key."
        )
        raise typer.Exit(EXIT_RUNTIME)


@hosts_app.command("show")
def hosts_show(host: str = typer.Argument(..., help="Host id, e.g. claude-code.")):
    """Show a single host's availability and which models target it."""
    st = hosts.detect_host(host)
    typer.echo(f"{host}: {st.availability} ({st.reason})")
    _, models = _load_registries()
    targeting = [m.key for m in models for t in m.execution_targets if t.host == host]
    typer.echo(f"Models using this host: {', '.join(targeting) or 'none'}")


# --- models (catalog inspection — Phase 3 CLI; refresh is handed off) ----------------


@models_app.command("list")
def models_list(
    available: bool = typer.Option(
        False, "--available", help="Only models with an available host."
    ),
):
    """List models grouped by vendor, with release channel and best host availability."""
    _, models = _load_registries()
    for m in sorted(models, key=lambda x: (x.vendor or "", x.model_id)):
        route = hosts.resolve_execution_route(m, include_unavailable=True)
        avail = route.status.availability if route.status else "unknown"
        if available and avail != hosts.AVAILABLE:
            continue
        typer.echo(
            f"{m.vendor_key:<34} {m.release_channel.value:<8} host={avail:<12} "
            f"ability(c/r/w)={m.ability.coding}/{m.ability.reasoning}/{m.ability.writing}"
        )


@models_app.command("show")
def models_show(
    key: str = typer.Argument(..., help="vendor/model_id, e.g. anthropic/claude-sonnet-5."),
):
    """Show one model: metadata, provenance, and execution targets."""
    _, models = _load_registries()
    m = next((x for x in models if x.vendor_key == key or x.key == key), None)
    if m is None:
        typer.echo(f"No model '{key}'. Try: agentrouter models list", err=True)
        raise typer.Exit(EXIT_USAGE)
    typer.echo(f"{m.name}  ({m.vendor_key})")
    typer.echo(
        f"  family={m.family}  release={m.release_channel.value}  snapshot={m.snapshot_type.value}"
    )
    typer.echo(
        f"  context={m.context_window:,}  max_output={m.max_output_tokens:,}  "
        f"pricing_tier={m.pricing_tier.value}"
    )
    typer.echo(
        f"  ability c/r/w = {m.ability.coding}/{m.ability.reasoning}/{m.ability.writing}"
        f"  (source={m.ability_source.value}, confidence={m.ability_confidence})"
    )
    typer.echo(f"  source={m.source}  verified={m.last_verified}")
    typer.echo("  execution targets:")
    for t in m.execution_targets:
        st = hosts.target_status(t)
        typer.echo(
            f"    - {t.host:<14} {t.execution_mode.value:<7} {st.availability:<12} {st.reason}"
        )


@app.command()
def execute(
    decision_id: str = typer.Argument(..., help="Decision id to execute, e.g. d_00042."),
    yes: bool = typer.Option(False, "--yes", help="Confirm running the recommended tool."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the exact command; run nothing."),
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
    legacy_opt_in = (
        provider is not None and provider.supports_execution and bool(provider.exec_command)
    )

    # Phase 7: when the vendor provider has NOT opted into the legacy exec_command
    # path, execute the exact model via its resolved execution host (Claude Code /
    # Codex CLI) if the decision carries a runnable execution_route.
    if not legacy_opt_in:
        er = payload.get("execution_route")
        if er and er.get("command_preview") and er.get("host_model_id"):
            _execute_via_host(rec, er, payload["prompt"], yes=yes, dry_run=dry_run)
            return

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
        completed = subprocess.run(argv)  # nosec B603 - argv list, shell=False, no string interpolation (test_execute_injection.py)
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
def server(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (localhost by default)."),
    port: int = typer.Option(8000, "--port", min=0, max=65535, help="Port."),
):
    """Run the local REST API (Phase P7). Remote model execution stays disabled.

    Set AGENTROUTER_API_KEY to require an X-API-Key header. Docs at /docs.
    Install extras first: pip install "agentrouter-os[server]".
    """
    try:
        import uvicorn

        from .server.app import app as api_app
    except ImportError as e:
        typer.echo(f"Server extras not installed: {e}", err=True)
        typer.echo('Next: pip install "agentrouter-os[server]"', err=True)
        raise typer.Exit(EXIT_RUNTIME) from e
    typer.echo(f"AgentRouter API on http://{host}:{port}  (docs: /docs)  — Ctrl+C to stop")
    uvicorn.run(api_app, host=host, port=port)


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

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_GOLD = _PROJECT_ROOT / "benchmarks" / "classifier_gold_v1.yaml"
_DEFAULT_ARTIFACTS = _PROJECT_ROOT / "artifacts"


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


# --- plugin (Phase P8) ---------------------------------------------------------


@plugin_app.command("list")
def plugin_list():
    """List installable host integrations and their current status."""
    for p in plugins.PLUGINS.values():
        typer.echo(f"{p.name:<12} [{plugins.status(p)}]  {p.description}")


def _resolve_plugin(name: str) -> plugins.Plugin:
    try:
        return plugins.get_plugin(name)
    except plugins.PluginError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(EXIT_USAGE) from e


@plugin_app.command("install")
def plugin_install(
    name: str = typer.Argument(..., help="Plugin name (see `plugin list`)."),
    force: bool = typer.Option(False, "--force", help="Back up and replace differing files."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the exact files, change nothing."),
):
    """Install a host integration (idempotent, reversible)."""
    p = _resolve_plugin(name)
    if dry_run:
        typer.echo(f"Would install '{p.name}':")
        for item in plugins.plan(p):
            typer.echo(f"  {item['action']:<24} {item['dest']}")
        return
    try:
        for r in plugins.install(p, force=force):
            typer.echo(f"  {r['result']:<28} {r['dest']}")
    except plugins.PluginError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(EXIT_RUNTIME) from e
    typer.echo(f"Installed '{p.name}'. Uninstall with: agentrouter plugin uninstall {p.name}")


@plugin_app.command("uninstall")
def plugin_uninstall(
    name: str = typer.Argument(..., help="Plugin name (see `plugin list`)."),
):
    """Remove a host integration; restores any backed-up user file."""
    p = _resolve_plugin(name)
    for r in plugins.uninstall(p):
        typer.echo(f"  {r['result']:<28} {r['dest']}")


@plugin_app.command("doctor")
def plugin_doctor():
    """Report install status and destination paths for every plugin."""
    for p in plugins.PLUGINS.values():
        typer.echo(f"{p.name}: {plugins.status(p)}  (root: {plugins.dest_root(p)})")
        for item in plugins.plan(p):
            typer.echo(f"  {item['action']:<24} {item['dest']}")


if __name__ == "__main__":
    app()
