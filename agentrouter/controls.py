"""Route-control filters (CLI_SPEC Phase P3).

User overrides that narrow the candidate model pool *before* ranking, plus a
preference -> weight mapping. Pure functions over the model list; the routing
engine is untouched. All vendor/host matching is case-insensitive. Backward
compatible: an empty ``RouteControls`` keeps every model (current default).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import hosts, taxonomy
from .schema import ModelEntry, ReleaseChannel

# Preference name -> weight vector (each sums to 1.0). A user preference is an
# explicit intent, so it overrides the engine's complexity/context weight shifts.
PREFERENCE_WEIGHTS: dict[str, dict[str, float]] = {
    "quality": {"w_cap": 0.65, "w_cost": 0.10, "w_lat": 0.10, "w_ctx": 0.15},
    "cheap": {"w_cap": 0.20, "w_cost": 0.55, "w_lat": 0.10, "w_ctx": 0.15},
    "fast": {"w_cap": 0.25, "w_cost": 0.15, "w_lat": 0.45, "w_ctx": 0.15},
    "balanced": {"w_cap": 0.45, "w_cost": 0.25, "w_lat": 0.15, "w_ctx": 0.15},
}


@dataclass(frozen=True)
class RouteControls:
    vendor: tuple[str, ...] = ()
    exclude_vendor: tuple[str, ...] = ()
    model: str | None = None
    host: tuple[str, ...] = ()
    exclude_host: tuple[str, ...] = ()
    max_price: float | None = None  # USD per 1M input tokens (None = no cap)
    stable_only: bool = False
    available_only: bool = False
    prohibit_tool: tuple[str, ...] = ()  # drop models that support any of these tools

    @property
    def active(self) -> bool:
        return any(
            [
                self.vendor,
                self.exclude_vendor,
                self.model,
                self.host,
                self.exclude_host,
                self.max_price is not None,
                self.stable_only,
                self.available_only,
                self.prohibit_tool,
            ]
        )


def _target_hosts(m: ModelEntry) -> set[str]:
    return {t.host.lower() for t in m.execution_targets}


def apply_controls(
    models: list[ModelEntry], c: RouteControls
) -> tuple[list[ModelEntry], list[dict]]:
    """Filter ``models`` by the user's route controls.

    Returns ``(kept, dropped)`` where each dropped entry is
    ``{"model": key, "reason": str}`` so the caller can fold it into the
    excluded-models display. Never mutates the input list.
    """
    if not c.active:
        return list(models), []

    vendor_in = {v.lower() for v in c.vendor}
    vendor_out = {v.lower() for v in c.exclude_vendor}
    host_in = {h.lower() for h in c.host}
    host_out = {h.lower() for h in c.exclude_host}
    model_pin = c.model.lower() if c.model else None

    kept: list[ModelEntry] = []
    dropped: list[dict] = []
    for m in models:
        reason = _reject_reason(m, c, vendor_in, vendor_out, host_in, host_out, model_pin)
        if reason:
            dropped.append({"model": m.key, "reason": f"control: {reason}"})
        else:
            kept.append(m)
    return kept, dropped


def _reject_reason(
    m: ModelEntry,
    c: RouteControls,
    vendor_in: set[str],
    vendor_out: set[str],
    host_in: set[str],
    host_out: set[str],
    model_pin: str | None,
) -> str | None:
    vkey = (m.vendor or m.provider or "").lower()
    if vendor_in and vkey not in vendor_in:
        return f"vendor '{m.vendor}' not in --vendor {sorted(vendor_in)}"
    if vendor_out and vkey in vendor_out:
        return f"vendor '{m.vendor}' excluded by --exclude-vendor"
    if model_pin and model_pin not in {m.vendor_key.lower(), m.key.lower(), m.model_id.lower()}:
        return f"does not match --model {c.model}"

    thosts = _target_hosts(m)
    if host_in and thosts.isdisjoint(host_in):
        return f"no execution target on --host {sorted(host_in)}"
    if host_out and not thosts.isdisjoint(host_out):
        return "execution host excluded by --exclude-host"

    if c.stable_only and m.release_channel is not ReleaseChannel.stable:
        return f"release channel '{m.release_channel.value}' is not stable (--stable-only)"

    if c.max_price is not None:
        price = m.input_price_per_million
        if price is None:
            # Honest cap: cannot guarantee under budget without a known price.
            return f"input price unknown; cannot verify --max-price {c.max_price}"
        if price > c.max_price:
            return f"input price ${price}/1M > --max-price ${c.max_price}"

    if c.available_only and not hosts.resolve_execution_route(m).is_available:
        return "no available execution host (--available-only)"

    if c.prohibit_tool:
        support = set(m.tool_support)
        banned = [t for t in c.prohibit_tool if support & taxonomy.equivalents(t)]
        if banned:
            return f"supports prohibited tool(s): {','.join(banned)}"

    return None
