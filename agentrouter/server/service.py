"""Business logic for the local REST surface (Phase P7).

Thin adapter over the existing classifier + engine + store + hosts modules so
the HTTP layer (app.py) stays declarative. No CLI private helpers are imported;
the registry loader below replicates the documented cli pattern.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from agentrouter import hosts, store
from agentrouter.classifier import classify
from agentrouter.engine import route as engine_route
from agentrouter.prompts import generate_prompt
from agentrouter.registry import load_all_models, load_providers
from agentrouter.safety import gates_for
from agentrouter.schema import Level, ModelEntry


def home() -> Path:
    return Path(os.environ.get("AGENTROUTER_HOME", Path.home() / ".agentrouter"))


def load_registry() -> list[ModelEntry]:
    """Load the model catalog. Raises RegistryError if the registry is missing/invalid."""
    h = home()
    providers = load_providers(h / "registry" / "providers.yaml")
    models, _warnings = load_all_models(h / "registry", providers)
    return models


def _execution_route(row: dict | None, models_by_key: dict[str, ModelEntry]) -> dict | None:
    """Stage-2 route block (mirrors cli._execution_route; no process is ever run)."""
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


def list_models() -> list[dict]:
    """Catalog view: vendor, model_id, release channel, context, best host availability."""
    models = load_registry()
    out = []
    for m in sorted(models, key=lambda x: (x.vendor or "", x.model_id)):
        resolved = hosts.resolve_execution_route(m, include_unavailable=True)
        avail = resolved.status.availability if resolved.status else "unknown"
        out.append(
            {
                "vendor": m.vendor,
                "model_id": m.model_id,
                "key": m.vendor_key,
                "release_channel": m.release_channel.value,
                "context_window": m.context_window,
                "host_availability": avail,
            }
        )
    return out


def list_hosts() -> list[dict]:
    """Availability for every known host (read-only; never runs a tool)."""
    return [
        {"host": name, "availability": st.availability, "reason": st.reason}
        for name in hosts.known_hosts()
        for st in (hosts.detect_host(name),)
    ]


def classify_task(
    task: str,
    *,
    context_tokens: int | None = None,
    risk: str | None = None,
    tools: list[str] | None = None,
) -> dict:
    cls = classify(
        task,
        context_tokens=context_tokens,
        risk=Level(risk) if risk else None,
        tools=tools,
    )
    return cls.model_dump(mode="json")


def route_task(
    task: str,
    *,
    prefer: str | None = None,
    context_tokens: int | None = None,
    risk: str | None = None,
    tools: list[str] | None = None,
    no_log: bool = False,
) -> dict:
    """Classify + route + resolve execution, mirroring the CLI decision payload."""
    models = load_registry()
    cls = classify(
        task,
        context_tokens=context_tokens,
        risk=Level(risk) if risk else None,
        tools=tools,
    )
    result = engine_route(models, cls, prefer=prefer)
    gates = gates_for(cls)

    rec = result["recommendation"]
    target = rec["model"] if rec else (result["manual_suggestion"] or "manual/human-operator")
    prompt = generate_prompt(task, target, cls, gates["checklist"])

    models_by_key = {m.key: m for m in models}
    exec_route = _execution_route(rec, models_by_key)
    fb_route = _execution_route(result["fallback"], models_by_key)

    payload = {
        "classification": cls.model_dump(mode="json"),
        **result,
        "gates": gates,
        "prompt": prompt,
        "execution_route": exec_route,
        "fallback_execution_route": fb_route,
    }
    decision_id = None
    if not no_log:
        conn = store.connect(home())
        decision_id = store.save_decision(conn, task, payload)
        conn.close()
    return {"decision_id": decision_id, "task": task, **payload}


def get_decision(decision_id: str) -> dict | None:
    conn = store.connect(home())
    payload = store.load_decision(conn, decision_id)
    conn.close()
    return payload


def save_feedback(decision_id: str, rating: int, note: str | None = None) -> bool:
    """Persist feedback into the existing `feedback` table (read by store.aggregate_stats).

    Returns False if the decision does not exist. Uses a raw INSERT on the shared
    connection rather than adding a new store function (ownership constraint).
    """
    conn = store.connect(home())
    try:
        if store.load_decision(conn, decision_id) is None:
            return False
        rowid = int(decision_id.removeprefix("d_"))
        conn.execute(
            "INSERT INTO feedback (decision_id, created_at, rating, note) VALUES (?, ?, ?, ?)",
            (rowid, datetime.now(timezone.utc).isoformat(), rating, note),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def execute_dry_run(decision_id: str) -> dict | None:
    """Return the execution plan (argv + preview) WITHOUT running anything.

    Remote/actual execution is disabled here by construction: this function never
    spawns a subprocess. It only reports what *would* run.
    """
    payload = get_decision(decision_id)
    if payload is None:
        return None
    rec = payload.get("recommendation")
    gates = payload.get("gates") or {}
    er = payload.get("execution_route")
    argv = None
    models = load_registry()
    if rec is not None:
        model = next((m for m in models if m.key == rec["model"]), None)
        if model is not None:
            resolved = hosts.resolve_execution_route(model, include_unavailable=True)
            if resolved.target and resolved.target.command_template:
                # argv with {prompt} left as a placeholder — never substituted, never run.
                argv = list(resolved.target.command_template)
    return {
        "decision_id": decision_id,
        "would_execute": False,
        "auto_execute_allowed": gates.get("auto_execute_allowed", False),
        "recommendation": rec,
        "execution_route": er,
        "argv": argv,
        "note": "dry-run only: no process was or will be spawned by this endpoint",
    }
