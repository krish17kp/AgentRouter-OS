"""Targeted regression tests that kill surviving mutants from the Linux mutation
campaign (TASK-010b). Each test names the exact production behaviour a survivor
would have silently broken. Grouped by module. Registered in
``[tool.mutmut].pytest_add_cli_args_test_selection`` so the campaign runs them.

These use injected clocks and direct access to internal structures where needed —
mutation testing rewards asserting exact boundary behaviour, not just happy paths.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

import agentrouter
from agentrouter import cli as cli_mod
from agentrouter import controls as controls_mod
from agentrouter import engine as engine_mod
from agentrouter import hosts as hosts_mod
from agentrouter.controls import RouteControls, apply_controls
from agentrouter.hosts import (
    AVAILABLE,
    UNAVAILABLE,
    UNKNOWN,
    command_preview,
    detect_host,
    execution_route_block,
    known_hosts,
    resolve_execution_route,
    target_status,
)
from agentrouter.registry import load_all_models, load_providers
from agentrouter.safety import gates_for
from agentrouter.schema import (
    Ability,
    ApprovalLevel,
    Classification,
    ContextBand,
    DeprecationStatus,
    ExecutionTarget,
    LatencyTier,
    Level,
    OutputType,
    PricingTier,
    ReleaseChannel,
    TaskType,
)
from agentrouter.server import limits as limits_mod
from agentrouter.server.limits import IdempotencyCache, RateLimiter

_SEEDS = Path(agentrouter.__file__).parent / "seeds"


def _seed_model(**over):
    """A real, fully-valid seed model with optional field overrides."""
    providers = load_providers(_SEEDS / "providers.yaml")
    models, _ = load_all_models(_SEEDS, providers)
    base = models[0]
    return base.model_copy(update=over) if over else base


def _classification(**over):
    kw = dict(
        task_type=TaskType.coding,
        complexity=Level.high,
        risk=Level.high,
        context_tokens=1000,
        context_band=ContextBand.small,
        output_type=OutputType.code,
        tool_needs=[],
        approval_level=ApprovalLevel.auto,
    )
    kw.update(over)
    return Classification(**kw)


# --------------------------------------------------------------------------- #
# agentrouter.server.limits — RateLimiter
# --------------------------------------------------------------------------- #


class _Clock:
    """Manually advanced monotonic clock."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def test_ratelimiter_window_floor_is_one_second():
    # kills check__mutmut_11: max(1, window) -> max(2, window).
    # With window=1 the counter must reset exactly one second later, not two.
    clk = _Clock(0.0)
    rl = RateLimiter(limit=1, window=1, clock=clk)
    assert rl.check("k") == (True, 0)
    clk.t = 0.5
    allowed, _ = rl.check("k")
    assert allowed is False  # still inside the 1s window
    clk.t = 1.0
    allowed, _ = rl.check("k")
    assert allowed is True  # window rolled over at exactly 1s (max(2,..) would block)


def test_ratelimiter_reset_count_starts_at_zero():
    # kills check__mutmut_22: reset `count = 0` -> `count = 1`.
    clk = _Clock(0.0)
    rl = RateLimiter(limit=1, window=10, clock=clk)
    assert rl.check("k")[0] is True
    assert rl.check("k")[0] is False
    clk.t = 10.0  # window expired -> reset
    # First request of the fresh window must be allowed (count 0->1, not 1->2).
    assert rl.check("k")[0] is True


def test_ratelimiter_retry_after_floor_is_one():
    # kills check__mutmut_38: max(1, remaining) -> max(2, remaining).
    clk = _Clock(0.0)
    rl = RateLimiter(limit=1, window=5, clock=clk)
    assert rl.check("k") == (True, 0)
    clk.t = 4.9  # remaining ~0.1 -> int()==0 -> floor to 1
    allowed, retry = rl.check("k")
    assert allowed is False
    assert retry == 1


def test_ratelimiter_retry_after_uses_elapsed_subtraction():
    # kills check__mutmut_40: window - (now-start) -> window + (now-start).
    clk = _Clock(0.0)
    rl = RateLimiter(limit=1, window=5, clock=clk)
    assert rl.check("k") == (True, 0)
    clk.t = 2.0
    allowed, retry = rl.check("k")
    assert allowed is False
    assert retry == 3  # 5 - 2, not 5 + 2


def test_ratelimiter_retry_after_uses_now_minus_start_not_plus():
    # kills check__mutmut_41: window - (now - start) -> window - (now + start).
    # Requires a non-zero window start, so drive the clock from an offset.
    clk = _Clock(100.0)
    rl = RateLimiter(limit=1, window=5, clock=clk)
    assert rl.check("k") == (True, 0)  # start = 100
    clk.t = 102.0
    allowed, retry = rl.check("k")
    assert allowed is False
    assert retry == 3  # 5 - (102-100); the mutant computes 5-(102+100) -> floors to 1


def test_ratelimiter_evicts_only_when_over_cap(monkeypatch):
    # kills check__mutmut_27: len > MAX -> len >= MAX (eviction trigger).
    monkeypatch.setattr(limits_mod, "MAX_ENTRIES", 2)
    clk = _Clock(0.0)
    rl = RateLimiter(limit=100, window=1000, clock=clk)
    # An expired bucket that must ONLY be dropped once we EXCEED the cap.
    rl._buckets["stale"] = (-10_000.0, 1)  # len 1, expired
    rl.check("a")  # adds "a" -> len == MAX (2); real code does not evict yet
    assert "stale" in rl._buckets  # `>=` mutant would have evicted it at ==MAX


def test_ratelimiter_evict_expiry_predicate(monkeypatch):
    # kills _evict_locked__mutmut_1 (now-s -> now+s) and __mutmut_2 (>= -> >).
    rl = RateLimiter(limit=1, window=5)
    rl._buckets = {"fresh": (3.0, 1)}  # now(3) - s(3) = 0 < window(5): keep
    rl._evict_locked(now=3.0, window=5)
    assert "fresh" in rl._buckets  # now+s (6>=5) would wrongly drop it
    rl._buckets = {"boundary": (0.0, 1)}  # now(5)-s(0) == window(5): expired -> drop
    rl._evict_locked(now=5.0, window=5)
    assert "boundary" not in rl._buckets  # `>` mutant keeps it


def test_ratelimiter_evict_stops_at_cap(monkeypatch):
    # kills _evict_locked__mutmut_3: while len > MAX -> while len >= MAX.
    monkeypatch.setattr(limits_mod, "MAX_ENTRIES", 2)
    rl = RateLimiter(limit=1, window=5)
    rl._buckets = {"a": (100.0, 1), "b": (100.0, 1)}  # neither expired at now=100
    rl._evict_locked(now=100.0, window=5)
    assert len(rl._buckets) == 2  # `>=` mutant would pop down to 1


# --------------------------------------------------------------------------- #
# agentrouter.server.limits — IdempotencyCache
# --------------------------------------------------------------------------- #


def _resp():
    return limits_mod.CachedResponse(status=200, body=b"{}", media_type="application/json")


def test_idempotency_get_expiry_is_exclusive_boundary():
    # kills get__mutmut_7: now-ts > ttl -> now-ts >= ttl.
    clk = _Clock(0.0)
    cache = IdempotencyCache(ttl=5, clock=clk)
    cache.put("k", _resp())
    clk.t = 5.0  # exactly ttl old -> still valid (strictly greater expires)
    assert cache.get("k") is not None  # `>=` mutant would expire it here


def test_idempotency_put_evicts_only_new_key_at_cap(monkeypatch):
    # kills put__mutmut_1: (new AND at cap) -> (new OR at cap).
    monkeypatch.setattr(limits_mod, "MAX_ENTRIES", 100)
    clk = _Clock(0.0)
    cache = IdempotencyCache(ttl=5, clock=clk)
    cache.put("a", _resp())
    clk.t = 100.0  # "a" is now expired but still stored (lazy)
    cache.put("b", _resp())  # new key, well under cap -> no eviction sweep
    assert "a" in cache._store  # `or` mutant would sweep expired "a" on every new put


def test_idempotency_evict_expiry_predicate():
    # kills _evict_locked__mutmut_2 (now-ts -> now+ts) and __mutmut_3 (> -> >=).
    clk = _Clock(3.0)
    cache = IdempotencyCache(ttl=5, clock=clk)
    cache._store = {"fresh": (3.0, _resp())}  # now-ts = 0 < ttl: keep
    cache._evict_locked()
    assert "fresh" in cache._store  # now+ts (6>5) mutant drops it
    clk.t = 5.0
    cache._store = {"boundary": (0.0, _resp())}  # now-ts == ttl: NOT expired (strict >)
    cache._evict_locked()
    assert "boundary" in cache._store  # `>=` mutant drops it


# --------------------------------------------------------------------------- #
# agentrouter.controls — apply_controls / _reject_reason
# --------------------------------------------------------------------------- #


def _reason_for(model, controls) -> str | None:
    kept, dropped = apply_controls([model], controls)
    if dropped:
        return dropped[0]["reason"]
    return None


def test_exclude_host_case_insensitive_drops_only_matching():
    # kills apply_controls 9/21 (host_out None), _reject_reason 21 (and->or),
    # 22 (isdisjoint inversion), 23 (isdisjoint(None)), 24/25 (reason text).
    on_host = _seed_model(execution_targets=[ExecutionTarget(host="codex-cli", host_model_id="x")])
    off_host = _seed_model(
        execution_targets=[ExecutionTarget(host="anthropic-api", host_model_id="y")]
    )
    kept, dropped = apply_controls([on_host, off_host], RouteControls(exclude_host=("CODEX-CLI",)))
    assert off_host in kept  # not on the excluded host -> kept (or-mutant would drop it)
    assert on_host not in kept  # on the excluded host -> dropped (invert-mutant would keep it)
    # Exact text (not substring) so an "XX..XX"-wrapped mutant is also killed.
    assert dropped[0]["reason"] == "control: execution host excluded by --exclude-host"


def test_dropped_entry_uses_model_key():
    # kills apply_controls 31 ("XXmodelXX") and 32 ("MODEL").
    m = _seed_model()
    _, dropped = apply_controls([m], RouteControls(vendor=("no-such-vendor",)))
    assert dropped and dropped[0]["model"] == m.key


def test_stable_only_keeps_stable_and_drops_prerelease():
    # kills _reject_reason 26 (and->or) and 27 (is not -> is).
    stable = _seed_model(release_channel=ReleaseChannel.stable)
    beta = _seed_model(release_channel=ReleaseChannel.preview)
    kept, _ = apply_controls([stable, beta], RouteControls(stable_only=True))
    assert stable in kept  # or-mutant / invert-mutant would drop the stable model
    assert beta not in kept
    # stable_only False must not drop the prerelease model (or-mutant would).
    kept2, _ = apply_controls([beta], RouteControls(vendor=(beta.vendor,)))
    assert beta in kept2


def test_max_price_boundary_is_inclusive():
    # kills _reject_reason 29 (price=None) and 31 (> -> >=).
    priced = _seed_model(input_price_per_million=5.0)
    kept, _ = apply_controls([priced], RouteControls(max_price=5.0))
    assert priced in kept  # price == cap is allowed; `>=` mutant / None-mutant drop it
    dear = _seed_model(input_price_per_million=5.01)
    kept2, _ = apply_controls([dear], RouteControls(max_price=5.0))
    assert dear not in kept2


def test_prohibit_tool_only_drops_supported_tools():
    # kills _reject_reason 40 (& -> |) and 43 (',' join separator).
    m = _seed_model()
    # A tool the model does NOT support must not cause rejection ('|' mutant drops it).
    kept, _ = apply_controls([m], RouteControls(prohibit_tool=("totally-unknown-tool",)))
    assert m in kept
    # Two supported, prohibited tools -> reason joins them with a bare comma.
    if len(m.tool_support) >= 2:
        two = tuple(m.tool_support[:2])
        reason = _reason_for(m, RouteControls(prohibit_tool=two))
        assert reason is not None
        assert "XX" not in reason  # kills the 'XX,XX' join mutant
        assert "," in reason


def test_vendor_key_prefers_vendor_then_provider():
    # kills _reject_reason 3, 4, 5 (vkey = (vendor or provider or "")).
    maker = _seed_model(vendor="maker", provider="host")
    # vkey must resolve to the vendor ("maker"); mutant 4 yields "host".
    assert maker in apply_controls([maker], RouteControls(vendor=("maker",)))[0]
    # vendor empty -> falls back to provider; mutant 3 yields "".
    prov_only = _seed_model(vendor="", provider="host")
    assert prov_only in apply_controls([prov_only], RouteControls(vendor=("host",)))[0]
    # both empty -> vkey is "" (not "XXXX"); mutant 5 would keep it under vendor=("xxxx",).
    empty = _seed_model(vendor="", provider="")
    kept, _ = apply_controls([empty], RouteControls(vendor=("xxxx",)))
    assert empty not in kept


def test_model_pin_matches_are_case_insensitive():
    # kills _reject_reason 13 (vendor_key.upper()) and 14 (key.upper()).
    m = _seed_model(vendor="maker", provider="host")  # vendor_key != key
    assert m in apply_controls([m], RouteControls(model=m.vendor_key.lower()))[0]
    assert m in apply_controls([m], RouteControls(model=m.key.lower()))[0]


def test_available_only_uses_host_availability(monkeypatch):
    # kills _reject_reason 33 (invert), 34 (resolve(None)), 35/36 (reason text).
    class _Route:
        def __init__(self, ok):
            self.is_available = ok

    m = _seed_model()
    # Availability keyed on identity so a resolve(None) mutant reads as unavailable.
    monkeypatch.setattr(
        controls_mod.hosts, "resolve_execution_route", lambda model: _Route(model is m)
    )
    assert m in apply_controls([m], RouteControls(available_only=True))[0]
    monkeypatch.setattr(controls_mod.hosts, "resolve_execution_route", lambda model: _Route(False))
    reason = _reason_for(m, RouteControls(available_only=True))
    # Exact text (not substring) so an "XX..XX"-wrapped mutant is also killed.
    assert reason == "control: no available execution host (--available-only)"


# --------------------------------------------------------------------------- #
# agentrouter.safety — gates_for (execution-safety invariant)
# --------------------------------------------------------------------------- #


def test_high_risk_never_auto_executes_even_when_approval_is_auto():
    # kills gates_for__mutmut_7: (not high AND auto) -> (not high OR auto).
    # The `or` mutant would allow auto-execution of a HIGH-RISK task — a bypass.
    g = gates_for(_classification(risk=Level.high, approval_level=ApprovalLevel.auto))
    assert g["auto_execute_allowed"] is False
    # Sanity: a low-risk auto task still auto-executes (pins the AND semantics).
    g2 = gates_for(_classification(risk=Level.low, approval_level=ApprovalLevel.auto))
    assert g2["auto_execute_allowed"] is True


# --------------------------------------------------------------------------- #
# agentrouter.hosts — detect_host / target_status
# --------------------------------------------------------------------------- #


def _target(**over):
    kw = dict(host="claude-code", host_model_id="x")
    kw.update(over)
    return ExecutionTarget(**kw)


def test_detect_host_manual_is_always_available():
    # kills detect_host 2/3 (host=="manual" text), 4 (host->None),
    # 6/10/11 (reason None/XX/UPPER).
    s = detect_host("manual")
    assert s.host == "manual"  # host arg preserved (mutant 4 -> None)
    assert s.availability == AVAILABLE
    assert s.reason == "manual execution is always available"


def test_detect_host_cli_available_and_unavailable(monkeypatch):
    # kills detect_host 12/13/14 (cmd resolution), 15/19 (or/and), 21-26 (args),
    # 27/29 (unavailable branch host/reason).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    s = detect_host("codex-cli")
    assert s.host == "codex-cli"
    assert s.availability == AVAILABLE
    assert s.reason == "'codex' found on PATH"  # cmd resolved via _CLI_HOSTS
    # Not on PATH -> UNAVAILABLE (mutant 19 `cmd or which` wrongly reports AVAILABLE).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: None)
    s2 = detect_host("codex-cli")
    assert s2.host == "codex-cli"
    assert s2.availability == UNAVAILABLE
    assert s2.reason == "'codex' not found on PATH"


def test_detect_host_required_command_for_unknown_host(monkeypatch):
    # kills detect_host 18 (host not in _API_HOSTS -> in): a host in neither dict
    # but with a required_command must still do a PATH check, not fall to UNKNOWN.
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    s = detect_host("custom-cli", required_command="mytool")
    assert s.availability == AVAILABLE
    assert s.reason == "'mytool' found on PATH"


def test_detect_host_api_available_and_unavailable(monkeypatch):
    # kills detect_host 36-44 (API branch host/availability/reason/args).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-xxx")
    s = detect_host("anthropic-api")
    assert s.host == "anthropic-api"
    assert s.availability == AVAILABLE
    assert s.reason == "ANTHROPIC_API_KEY is set"  # value never printed
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s2 = detect_host("anthropic-api")
    assert s2.host == "anthropic-api"
    assert s2.availability == UNAVAILABLE
    assert s2.reason == "ANTHROPIC_API_KEY is not set"


def test_detect_host_unrecognized_is_unknown():
    # kills detect_host 48 (host->None), 50 (reason None), 54/55 (reason XX/UPPER).
    s = detect_host("nope-nonexistent-host")
    assert s.host == "nope-nonexistent-host"
    assert s.availability == UNKNOWN
    assert s.reason == "unrecognized host; cannot verify availability"


def test_target_status_forwards_host_and_command(monkeypatch):
    # kills target_status 1 (host->None), 2 (required_command->None), 3/4 (arg drop).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: None)
    t = _target(host="custom-cli", required_command="zzcli")
    s = target_status(t)
    assert s.host == "custom-cli"  # t.host forwarded (mutant 1 -> None)
    assert s.reason == "'zzcli' not found on PATH"  # t.required_command forwarded (mutant 2)


# --------------------------------------------------------------------------- #
# agentrouter.hosts — resolve_execution_route
# --------------------------------------------------------------------------- #


def test_resolve_prefers_available_target(monkeypatch):
    # kills resolve 11 (== -> !=), 12 (target->None), 13 (status->None).
    monkeypatch.setattr(
        hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}" if c == "codex" else None
    )
    avail = _target(host="codex-cli", host_model_id="a")  # codex on PATH
    m = _seed_model(execution_targets=[avail])
    r = resolve_execution_route(m)
    assert r.target is avail  # picks the available one (mutant 12 -> None)
    assert r.status is not None and r.status.availability == AVAILABLE  # mutant 13 -> None
    assert r.is_available is True


def test_resolve_default_hides_unavailable_target(monkeypatch):
    # kills resolve 1 (default include_unavailable True->... ) and 26 (statuses[0]->[1]).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: None)
    only = _target(host="codex-cli", host_model_id="a")  # not on PATH -> unavailable
    m = _seed_model(execution_targets=[only])
    r = resolve_execution_route(m)  # default include_unavailable=False
    assert r.target is None  # unavailable hidden by default (mutant 1 default True exposes it)
    assert r.status is not None  # statuses[0]; mutant 26 statuses[1] -> IndexError
    assert r.is_available is False
    # include_unavailable=True exposes the global-best-but-unrunnable target.
    r2 = resolve_execution_route(m, include_unavailable=True)
    assert r2.target is only


def test_resolve_no_targets_returns_empty(monkeypatch):
    # kills resolve 27 (all_statuses None), 28/29/30 (arg-drop TypeError).
    m = _seed_model(execution_targets=[])
    r = resolve_execution_route(m)
    assert r.target is None
    assert r.status is None
    assert r.all_statuses == []  # mutant 27 -> None


# --------------------------------------------------------------------------- #
# agentrouter.hosts — command_preview / known_hosts
# --------------------------------------------------------------------------- #


def test_command_preview_redacts_prompt_by_default():
    # kills command_preview 1 (default redact False), 4 (XX-wrap), 6 (and->or), 11 (join).
    t = _target(command_template=["codex", "run", "{prompt}"])
    assert command_preview(t) == "codex run <prompt redacted>"  # default redacts
    # redact=True must leave non-prompt args intact (mutant 6 `or` redacts everything).
    assert command_preview(t, redact=True) == "codex run <prompt redacted>"
    # redact=False shows the raw template joined by a single space (mutant 1 & 11).
    assert command_preview(t, redact=False) == "codex run {prompt}"


def test_known_hosts_includes_manual():
    # kills known_hosts 1 ("XXmanualXX").
    assert "manual" in known_hosts()
    assert "claude-code" in known_hosts()


# --------------------------------------------------------------------------- #
# agentrouter.hosts — execution_route_block
# --------------------------------------------------------------------------- #


def test_execution_route_block_missing_model_returns_none():
    # kills execution_route_block 6 (or -> and): a missing model must short-circuit
    # to None, not dereference model.execution_targets (AttributeError).
    assert execution_route_block({"model": "no-such-key"}, {}) is None
    assert execution_route_block(None, {}) is None


def test_execution_route_block_payload_keys_and_values(monkeypatch):
    # kills execution_route_block 28/29,34/35,41/42,45/46,47-52 (dict key/value text).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    t = _target(
        host="codex-cli",
        host_model_id="hmi",
        command_template=["codex", "{prompt}"],
        required_env=["FOO"],
    )
    m = _seed_model(execution_targets=[t])
    block = execution_route_block({"model": m.key}, {m.key: m})
    assert block is not None
    # Exact key set pins every "XX"/UPPER key mutant.
    for key in (
        "execution_mode",
        "availability",
        "availability_reason",
        "required_env",
        "max_output_tokens",
        "all_hosts",
    ):
        assert key in block
    assert block["max_output_tokens"] == m.max_output_tokens
    assert block["required_env"] == ["FOO"]
    assert block["availability"] == AVAILABLE
    # all_hosts entries use lowercase host/availability keys (mutants 49-52).
    assert block["all_hosts"] == [{"host": "codex-cli", "availability": AVAILABLE}]


# --------------------------------------------------------------------------- #
# agentrouter.cli._execute_via_host — gated host execution (execution-bypass)
# --------------------------------------------------------------------------- #
#
# _execute_via_host resolves HOW to run the exact model and is a subprocess
# boundary, so every branch and message matters. These call it directly with an
# injected registry so each exit path is exercised deterministically. `er` is
# unused by the body, so an empty dict is fine.


def _host_model(**over):
    return _seed_model(**over)


def _call_via_host(monkeypatch, model, *, prompt="the-prompt", yes=False, dry_run=False):
    monkeypatch.setattr(cli_mod, "_load_registries", lambda: ({}, [model]))
    with pytest.raises(typer.Exit) as ei:
        cli_mod._execute_via_host({"model": model.key}, {}, prompt, yes=yes, dry_run=dry_run)
    return ei.value.exit_code


def test_execute_via_host_missing_model(monkeypatch, capfd):
    # kills 5 (next default), 10-16 (message/err/stream), 17 (Exit code).
    m = _host_model(execution_targets=[ExecutionTarget(host="manual", host_model_id="x")])
    monkeypatch.setattr(cli_mod, "_load_registries", lambda: ({}, [m]))
    with pytest.raises(typer.Exit) as ei:
        cli_mod._execute_via_host({"model": "no-such-model"}, {}, "p", yes=True, dry_run=False)
    assert ei.value.exit_code == 2  # EXIT_USAGE (mutant 17 -> None)
    err = capfd.readouterr().err
    assert "is no longer in the registry" in err  # on stderr (mutants 11/13/16 -> stdout/None)


def test_execute_via_host_found_model_is_exact(monkeypatch, capfd):
    # kills 6 (m.key == -> !=): the resolved model must be the requested one.
    right = _host_model(execution_targets=[ExecutionTarget(host="manual", host_model_id="x")])
    code = _call_via_host(monkeypatch, right, dry_run=True)
    assert code == 0
    out = capfd.readouterr().out
    assert right.name in out  # `!=` mutant would pick a different/none model


def test_execute_via_host_no_target(monkeypatch, capfd):
    # kills 28-33 (No-execution-target message/err/stream + Exit code).
    m = _host_model(execution_targets=[])
    with pytest.raises(typer.Exit) as ei:
        monkeypatch.setattr(cli_mod, "_load_registries", lambda: ({}, [m]))
        cli_mod._execute_via_host({"model": m.key}, {}, "p", yes=True, dry_run=False)
    assert ei.value.exit_code == 2
    err = capfd.readouterr().err
    assert "No execution target" in err


def test_execute_via_host_dry_run_previews(monkeypatch, capfd):
    # kills 34/36/37 (echo None for Model/Availability/Command), 40 (Dry run text),
    # 43 (Exit code 0).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    m = _host_model(
        execution_targets=[
            ExecutionTarget(
                host="codex-cli", host_model_id="x", command_template=["codex", "{prompt}"]
            )
        ]
    )
    code = _call_via_host(monkeypatch, m, dry_run=True)
    assert code == 0  # mutant 43 -> None
    out = capfd.readouterr().out
    assert "Model:" in out  # mutant 34 echo(None) drops it
    assert "Availability:" in out  # mutant 36
    assert "Command:" in out  # mutant 37
    assert "Dry run: nothing executed." in out
    assert "XX" not in out  # mutant 40 wraps the string in XX...XX


def test_execute_via_host_no_command_template(monkeypatch, capfd):
    # kills 46 (echo None), 47/48/49 (message text), 50 (Exit None), 51 (Exit 1 vs 0).
    m = _host_model(
        execution_targets=[ExecutionTarget(host="manual", host_model_id="x")]  # no command_template
    )
    code = _call_via_host(monkeypatch, m, yes=True, dry_run=False)
    assert code == 0  # manual host with no command exits cleanly (mutant 51 -> 1)
    out = capfd.readouterr().out
    assert "use the vendor API/SDK with the generated prompt." in out
    assert "XX" not in out  # mutant 47 wraps the string in XX...XX


def test_execute_via_host_refuses_unavailable(monkeypatch, capfd):
    # kills 53-65 (Not-enabled + Next messages, err streams, text).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: None)  # codex not on PATH
    m = _host_model(
        execution_targets=[
            ExecutionTarget(
                host="codex-cli", host_model_id="x", command_template=["codex", "{prompt}"]
            )
        ]
    )
    code = _call_via_host(monkeypatch, m, yes=True, dry_run=False)
    assert code == 2  # never executes an unavailable host
    err = capfd.readouterr().err
    assert "Not enabled: host 'codex-cli' is unavailable." in err
    assert "Next: install/authenticate the host, or run the generated prompt yourself." in err
    assert "XX" not in err  # mutant 62 wraps the string in XX...XX


def test_execute_via_host_requires_yes(monkeypatch, capfd):
    # kills 67 (`if not yes` -> `if yes`: a missing --yes MUST NOT execute),
    # 68/69/70/71 (Next message text), 72 (Exit code).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    ran = {"v": False}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: ran.__setitem__("v", True))
    m = _host_model(
        execution_targets=[
            ExecutionTarget(
                host="codex-cli", host_model_id="x", command_template=["true", "{prompt}"]
            )
        ]
    )
    code = _call_via_host(monkeypatch, m, yes=False, dry_run=False)
    assert code == 2  # EXIT_USAGE; mutant 67 would fall through and execute
    assert ran["v"] is False  # nothing ran without --yes (mutant 67 execution bypass)
    out = capfd.readouterr().out
    assert "Next: re-run with --yes to execute (or --dry-run to preview)." in out
    assert "XX" not in out  # mutant 69 wraps the string in XX...XX


def test_execute_via_host_substitutes_prompt_and_propagates_code(monkeypatch, capfd):
    # kills 73-79 (argv/replace), 80 (Running echo), 81/82 (subprocess.run), 95 (exit code).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    script = "import sys; sys.stdout.write(sys.argv[1]); sys.exit(7)"
    m = _host_model(
        execution_targets=[
            ExecutionTarget(
                host="codex-cli",
                host_model_id="x",
                command_template=[sys.executable, "-c", script, "{prompt}"],
            )
        ]
    )
    code = _call_via_host(monkeypatch, m, prompt="MARKER123", yes=True, dry_run=False)
    assert code == 7  # completed.returncode propagated (mutant 95 -> None)
    cap = capfd.readouterr()
    assert "Running" in cap.out  # mutant 80 echo(None)
    assert "MARKER123" in cap.out  # {prompt} substituted (mutants 78/79 leave it literal)


def test_execute_via_host_file_not_found(monkeypatch, capfd):
    # kills 83-93 (failure messages/err/stream, argv[0] vs argv[1]), 94 (Exit code).
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    m = _host_model(
        execution_targets=[
            ExecutionTarget(
                host="codex-cli",
                host_model_id="x",
                required_command="ghostbin",
                command_template=["definitely-not-a-real-binary-xyz", "{prompt}"],
            )
        ]
    )
    code = _call_via_host(monkeypatch, m, prompt="p", yes=True, dry_run=False)
    assert code == 1  # EXIT_RUNTIME (mutant 94 -> None)
    err = capfd.readouterr().err
    # argv[0] is the missing binary; mutant 87 (argv[1]) would print the prompt instead.
    assert "Execution failed: command not found: definitely-not-a-real-binary-xyz" in err
    assert "Next: install the 'codex-cli' CLI (ghostbin)." in err


# --------------------------------------------------------------------------- #
# agentrouter.engine — routing math (routing_engine group)
# --------------------------------------------------------------------------- #


def _emodel(**over):
    """Seed model with engine-relevant overrides (real ModelEntry)."""
    return _seed_model(**over)


def _cls_e(**over):
    kw = dict(
        task_type=TaskType.general,
        complexity=Level.medium,
        risk=Level.low,
        context_tokens=10_000,
        context_band=ContextBand.small,
    )
    kw.update(over)
    return _classification(**kw)


# --- weights_for ---


def test_weights_high_complexity_or_risk():
    # kills 7 (or->and), 9 (risk is not high), 11-16 (keys/values), 18/19 (shift text).
    hi = {"w_cap": 0.55, "w_cost": 0.15, "w_lat": 0.15, "w_ctx": 0.15}
    w, shifts = engine_mod.weights_for(_cls_e(complexity=Level.high, risk=Level.low))
    assert w == hi  # complexity=high alone triggers it (mutant 7 `and` would not)
    assert shifts == ["complexity/risk=high -> w_cap 0.55, w_cost 0.15"]
    w2, _ = engine_mod.weights_for(_cls_e(complexity=Level.medium, risk=Level.high))
    assert w2 == hi  # risk=high alone triggers it (mutant 9 would not)


def test_weights_medium_is_base():
    # kills 8 (complexity is not high): a medium/low task keeps the base weights.
    base = {"w_cap": 0.45, "w_cost": 0.25, "w_lat": 0.15, "w_ctx": 0.15}
    w, shifts = engine_mod.weights_for(_cls_e(complexity=Level.medium, risk=Level.low))
    assert w == base
    assert shifts == []


def test_weights_low_complexity():
    # kills 20 (is not low), 22-27 (keys/values), 29/30 (shift text).
    w, shifts = engine_mod.weights_for(_cls_e(complexity=Level.low, risk=Level.low))
    assert w == {"w_cap": 0.35, "w_cost": 0.35, "w_lat": 0.15, "w_ctx": 0.15}
    assert shifts == ["complexity=low -> w_cap 0.35, w_cost 0.35"]


def test_weights_large_context():
    # kills 31 (is not large), 33-38 (keys/values), 39/40/41 (shift text).
    w, shifts = engine_mod.weights_for(
        _cls_e(complexity=Level.medium, context_band=ContextBand.large)
    )
    assert w == {"w_cap": 0.45, "w_cost": 0.25, "w_lat": 0.05, "w_ctx": 0.25}
    assert shifts == ["context=large -> w_ctx 0.25, w_lat 0.05"]
    # a small-context task must NOT get the large shift (mutant 31 would apply it).
    w2, _ = engine_mod.weights_for(_cls_e(complexity=Level.medium, context_band=ContextBand.small))
    assert w2["w_ctx"] == 0.15 and w2["w_lat"] == 0.15


# --- eligibility ---


def test_eligibility_retired_excluded_with_exact_reason():
    # kills 6/7 (reason key), 8/9 (reason value).
    m = _emodel(model_id="ret", deprecation_status=DeprecationStatus.retired)
    eligible, excluded = engine_mod.eligibility([m], _cls_e())
    assert eligible == []
    assert excluded == [{"model": m.key, "reason": "retired"}]


def test_eligibility_context_boundary_is_inclusive():
    # kills 11 (< -> <=): context_window exactly equal to the ask must stay eligible.
    m = _emodel(
        model_id="exact", context_window=10_000, deprecation_status=DeprecationStatus.active
    )
    eligible, _ = engine_mod.eligibility([m], _cls_e(context_tokens=10_000))
    assert m in eligible


def test_eligibility_continue_not_break_retired():
    # a good model AFTER an excluded (retired) one must survive.
    bad = _emodel(model_id="bad", deprecation_status=DeprecationStatus.retired)
    good = _emodel(model_id="good", deprecation_status=DeprecationStatus.active)
    eligible, _ = engine_mod.eligibility([bad, good], _cls_e())
    assert good in eligible  # `break` would drop everything after `bad`


def test_eligibility_context_filter_continues():
    # kills 17 (continue -> break) on the context filter: a good model after a
    # context-excluded one must survive.
    small = _emodel(
        model_id="small", context_window=100, deprecation_status=DeprecationStatus.active
    )
    good = _emodel(
        model_id="bigctx", context_window=1_000_000, deprecation_status=DeprecationStatus.active
    )
    eligible, _ = engine_mod.eligibility([small, good], _cls_e(context_tokens=50_000))
    assert good in eligible  # `break` after the small model would drop `good`


def test_eligibility_continue_not_break_context():
    # kills 37-analogue via context path already; here pins the missing-tools branch.
    bad = _emodel(model_id="notools", tool_support=[], deprecation_status=DeprecationStatus.active)
    good = _emodel(
        model_id="tools",
        tool_support=["file-edit", "shell"],
        deprecation_status=DeprecationStatus.active,
    )
    eligible, excluded = engine_mod.eligibility(
        [bad, good], _cls_e(tool_needs=["file-edit", "shell"])
    )
    assert good in eligible  # `break` (mutant 37) would drop `good`
    # exact reason incl. bare-comma join (mutants 33/34 key, 36 join separator).
    bad_reason = next(e["reason"] for e in excluded if e["model"] == bad.key)
    assert bad_reason == "missing tools: file-edit,shell"


def test_eligibility_vision_excluded_with_exact_reason():
    # kills 46/47 (reason key), 48/49 (value), 50 (continue -> break).
    bad = _emodel(
        model_id="novis", vision_support=False, deprecation_status=DeprecationStatus.active
    )
    good = _emodel(model_id="vis", vision_support=True, deprecation_status=DeprecationStatus.active)
    eligible, excluded = engine_mod.eligibility([bad, good], _cls_e(tool_needs=["vision"]))
    assert good in eligible  # break would drop `good`
    assert {"model": bad.key, "reason": "no vision support"} in excluded


# --- _capability_match / _context_fit / _use_case_adjust ---


def test_capability_match_blend_and_divisor():
    # kills 3 (* -> /) and 9 (/10 -> /11).
    m = _emodel(ability=Ability(coding=8, reasoning=4, writing=2))
    # coding task: blend {coding:1.0} -> 8/10 = 0.8.
    assert engine_mod._capability_match(m, _cls_e(task_type=TaskType.coding)) == pytest.approx(0.8)
    # analysis task: 0.7*reasoning + 0.3*writing over /10 (mutant `/w` would divide by weight).
    got = engine_mod._capability_match(m, _cls_e(task_type=TaskType.analysis))
    assert got == pytest.approx(0.7 * 4 / 10 + 0.3 * 2 / 10)


@pytest.mark.parametrize(
    "window,tokens,expected",
    [
        (2, 1, 1.0),  # ratio 2 -> comfortable (kills 7 max-default, 8 `<=2`)
        (3, 2, 0.7),  # ratio 1.5 -> barely fits (kills 10 return value)
        (25, 10, 1.0),  # ratio 2.5 (kills 9 `<3`)
        (100, 10, 1.0),  # ratio 10 (kills 13 return value)
        (160, 10, 0.6),  # ratio 16 -> oversized (kills 11 `<=16`, 12 `<17`, 14 return value)
        (8, 2, 1.0),  # ratio 4 (kills 2 `/`->`*`)
    ],
)
def test_context_fit_boundaries(window, tokens, expected):
    m = _emodel(context_window=window)
    assert engine_mod._context_fit(m, _cls_e(context_tokens=tokens)) == pytest.approx(expected)


def test_use_case_adjust_signs():
    # kills 2 (adj=1.0), 3 (in ideal), 5 (+= -> -=), 6 (in avoid), 7 (-= -> =), 8 (-= -> +=).
    coding = _cls_e(task_type=TaskType.coding)
    neither = _emodel(ideal_use_cases=[], avoid_use_cases=[])
    assert engine_mod._use_case_adjust(neither, coding) == 0.0
    ideal = _emodel(ideal_use_cases=["coding"], avoid_use_cases=[])
    assert engine_mod._use_case_adjust(ideal, coding) == pytest.approx(0.05)
    avoid = _emodel(ideal_use_cases=[], avoid_use_cases=["coding"])
    assert engine_mod._use_case_adjust(avoid, coding) == pytest.approx(-0.10)


# --- score_models ---


def test_score_models_exact_terms_and_score():
    # kills sign mutants (24/25/26/37), round/drop/key mutants (54-92) and 99.
    m = _emodel(
        model_id="scored",
        ability=Ability(coding=5, reasoning=5, writing=6),  # general blend -> 0.5333...
        pricing_tier=PricingTier.medium,
        latency_tier=LatencyTier.medium,
        context_window=15_000,  # ratio 1.5 -> ctx 0.7 (non-integer: kills `*`->`/` and round->int)
        ideal_use_cases=["general"],  # adj +0.05 (non-zero so `+adj`->`-adj` shows)
        avoid_use_cases=[],
        deprecation_status=DeprecationStatus.active,
    )
    cls = _cls_e(task_type=TaskType.general, complexity=Level.high, context_tokens=10_000)
    weights = {"w_cap": 0.55, "w_cost": 0.15, "w_lat": 0.15, "w_ctx": 0.15}

    cap = sum(
        getattr(m.ability, d) / 10 * wt for d, wt in engine_mod._CAP_BLEND[cls.task_type].items()
    )
    cost = engine_mod._COST_FIT[cls.complexity][m.pricing_tier]
    lat = engine_mod._LAT_FIT[cls.complexity][m.latency_tier]
    ctx = engine_mod._context_fit(m, cls)
    adj = engine_mod._use_case_adjust(m, cls)
    dep = 0.0
    score = (
        weights["w_cap"] * cap
        + weights["w_cost"] * cost
        + weights["w_lat"] * lat
        + weights["w_ctx"] * ctx
        + adj
        - dep
    )
    row = engine_mod.score_models([m], cls, weights)[0]
    assert row["terms"] == {
        "cap": round(cap, 2),
        "cost": round(cost, 2),
        "lat": round(lat, 2),
        "ctx": round(ctx, 2),
        "adj": round(adj, 2),
        "dep": round(dep, 2),
    }
    assert row["score"] == round(score, 3)  # round(,4) mutant differs on the 4th decimal


def test_score_models_deprecation_penalty_term():
    # kills 89/91 (round(dep, None)/round(dep,) -> int): a deprecated model has dep=0.2,
    # which round-to-int would collapse to 0.
    m = _emodel(model_id="dep", deprecation_status=DeprecationStatus.deprecated)
    weights = {"w_cap": 0.45, "w_cost": 0.25, "w_lat": 0.15, "w_ctx": 0.15}
    row = engine_mod.score_models([m], _cls_e(), weights)[0]
    assert row["terms"]["dep"] == 0.2  # _DEPRECATION_PENALTY; round(0.2) would be 0


# --- pick_fallback ---


def _fbrow(key, model_id, provider, tier):
    return {"model": key, "model_id": model_id, "provider": provider, "pricing_tier": tier.value}


def _fbmodel(model_id, provider, tier, fallback=()):
    key = f"{provider}/{model_id}"
    return SimpleNamespace(
        key=key, model_id=model_id, provider=provider, pricing_tier=tier, fallback=list(fallback)
    )


def test_pick_fallback_meaningful_diff_uses_immediate_second():
    # kills 16 (ranked[1:] -> ranked[2:]) in the "best remaining" loop.
    rec = _fbmodel("a", "pa", PricingTier.high)
    b = _fbmodel("b", "pb", PricingTier.high)
    c = _fbmodel("c", "pc", PricingTier.high)
    ranked = [
        _fbrow(rec.key, "a", "pa", PricingTier.high),
        _fbrow(b.key, "b", "pb", PricingTier.high),
        _fbrow(c.key, "c", "pc", PricingTier.high),
    ]
    mbk = {rec.key: rec, b.key: b, c.key: c}
    ids = {"a", "b", "c"}
    fb = engine_mod.pick_fallback(ranked, mbk, ids)
    assert fb["model"] == b.key  # mutant 16 would skip b and return c


def test_pick_fallback_declared_list_first():
    # kills 6 (ranked[1:] -> ranked[2:]) in the declared-fallback loop.
    rec = _fbmodel("a", "pa", PricingTier.high, fallback=["b"])
    b = _fbmodel("b", "pa", PricingTier.high)  # same provider+tier: NOT a "meaningful diff"
    c = _fbmodel("c", "pc", PricingTier.low)
    ranked = [
        _fbrow(rec.key, "a", "pa", PricingTier.high),
        _fbrow(b.key, "b", "pa", PricingTier.high),
        _fbrow(c.key, "c", "pc", PricingTier.low),
    ]
    mbk = {rec.key: rec, b.key: b, c.key: c}
    ids = {"a", "b", "c"}
    fb = engine_mod.pick_fallback(ranked, mbk, ids)
    # declared fallback 'b' wins; mutant 6 skips b, then step-2 returns c instead.
    assert fb["model"] == b.key


# --- route ---


def test_route_passes_base_weights_through():
    # kills 3 (weights_for(cls, None, prefer) drops base_weights).
    m = _emodel(model_id="r1", deprecation_status=DeprecationStatus.active)
    base = {"w_cap": 0.90, "w_cost": 0.05, "w_lat": 0.03, "w_ctx": 0.02}
    out = engine_mod.route([m], _cls_e(complexity=Level.medium, risk=Level.low), base_weights=base)
    assert out["weights"] == base  # mutant 3 would fall back to BASE_WEIGHTS


def test_route_manual_suggestion_when_none_eligible():
    # kills 15 (manual=None), 19 (provider !=), 20/21 (manual text),
    # 22-29 (no-eligible dict keys).
    manual = _emodel(model_id="m", provider="manual", context_window=10)
    other = _emodel(model_id="o", provider="openai", context_window=10)
    out = engine_mod.route([manual, other], _cls_e(context_tokens=1_000_000))
    assert out["scores"] == []  # nothing eligible
    assert out["manual_suggestion"] == manual.key  # mutants 15/19/20/21 break this
    for key in ("weights", "weight_shifts", "scores", "manual_suggestion"):
        assert key in out


def test_route_eligible_payload_keys():
    # kills 51/52 (weights key) and 64/65 (manual_suggestion key) on the happy path.
    m = _emodel(model_id="r2", deprecation_status=DeprecationStatus.active)
    out = engine_mod.route([m], _cls_e())
    assert out["recommendation"] is not None
    for key in (
        "weights",
        "weight_shifts",
        "scores",
        "recommendation",
        "fallback",
        "manual_suggestion",
    ):
        assert key in out


# --------------------------------------------------------------------------- #
# agentrouter.cli._execute — the execute() command's gate + dispatch
# --------------------------------------------------------------------------- #
#
# execute() delegates to this undecorated helper so its safety-critical logic
# (high-risk block, provider opt-in gate, host dispatch) is reachable by mutation
# testing. These call _execute directly with store + registries stubbed out.


def _prov(supports_execution=True, exec_command=("true",)):
    return SimpleNamespace(
        id="prov", supports_execution=supports_execution, exec_command=list(exec_command)
    )


def _payload(**over):
    p = {
        "gates": {"auto_execute_allowed": True, "approval_level": "auto"},
        "classification": {"risk": "low"},
        "recommendation": {"model": "prov/m", "provider": "prov"},
        "prompt": "the-prompt",
        "execution_route": None,
    }
    p.update(over)
    return p


def _run_execute(
    monkeypatch,
    tmp_path,
    payload,
    *,
    recent=(),
    providers=None,
    models=(),
    yes=False,
    dry_run=False,
    decision_id="d_1",
):
    monkeypatch.setattr(cli_mod, "_home", lambda: tmp_path)
    monkeypatch.setattr(cli_mod.store, "connect", lambda home: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(cli_mod.store, "load_decision", lambda conn, did: payload)
    monkeypatch.setattr(cli_mod.store, "recent_ids", lambda conn: list(recent))
    monkeypatch.setattr(cli_mod, "_load_registries", lambda: (providers or {}, list(models)))
    with pytest.raises(typer.Exit) as ei:
        cli_mod._execute(decision_id, yes=yes, dry_run=dry_run)
    return ei.value.exit_code


def test_execute_not_found_lists_recent(monkeypatch, tmp_path, capfd):
    # kills 8 (recent=None), 11-15 (message/err/stream), 16-22 (recent msg/join).
    code = _run_execute(monkeypatch, tmp_path, None, recent=["d_a", "d_b"])
    assert code == 2
    err = capfd.readouterr().err
    assert "No decision found with id 'd_1'." in err
    assert "Next: try a recent id: d_a, d_b" in err  # recent=None mutant drops this line
    assert "XX" not in err  # kills the 'XX, XX'.join mutant


def test_execute_high_risk_blocked_messages(monkeypatch, tmp_path, capfd):
    # kills 31/33/34 (blocked msg), 35-38 (Why echo), 45-55 (Why/Next text + streams).
    payload = _payload(
        gates={"auto_execute_allowed": False, "approval_level": "human-approval-required"},
        classification={"risk": "high"},
    )
    code = _run_execute(monkeypatch, tmp_path, payload, yes=True)
    assert code == 2  # high risk provably blocked even with --yes
    err = capfd.readouterr().err
    assert "Execution blocked for d_1." in err
    assert "Why: risk=high, approval=human-approval-required" in err
    assert "the task themselves (NFR-8: high risk never auto-executes)." in err
    assert "Next: agentrouter prompt generate --from d_1 --out prompt.md" in err
    assert "and run the tool yourself." in err
    assert "XX" not in err


def test_execute_no_recommendation(monkeypatch, tmp_path, capfd):
    # kills 61-68 (message/err/stream) and 69 (Exit code).
    code = _run_execute(monkeypatch, tmp_path, _payload(recommendation=None))
    assert code == 2
    err = capfd.readouterr().err
    assert "Nothing to execute: this decision had no eligible model." in err
    assert "XX" not in err


def test_execute_provider_none_not_enabled(monkeypatch, tmp_path, capfd):
    # kills 106 (is None and -> crash), 110-141 (not-enabled msgs, Path ops, text).
    code = _run_execute(monkeypatch, tmp_path, _payload(), providers={})
    assert code == 2
    err = capfd.readouterr().err
    assert "Execution is not enabled for provider 'prov'." in err
    assert "Why: execution is opt-in per provider; it needs supports_execution: true" in err
    assert "AND an exec_command in registry/providers.yaml." in err
    assert "Next: edit" in err
    # The exact home path pins the registry/providers.yaml path components (mutants
    # 132-137: Path `/`->`*`, and the registry/providers.yaml casing).
    assert str(tmp_path / "registry" / "providers.yaml") in err
    assert "to opt in, or run the" in err
    assert "generated prompt yourself." in err
    assert "XX" not in err


def test_execute_provider_supports_but_no_command(monkeypatch, tmp_path, capfd):
    # kills 105 (or not exec -> and not exec): supports_execution but empty exec_command
    # must still be "not enabled", not fall through to "Would run".
    providers = {"prov": _prov(supports_execution=True, exec_command=[])}
    code = _run_execute(monkeypatch, tmp_path, _payload(), providers=providers, yes=False)
    assert code == 2
    err = capfd.readouterr().err
    assert "Execution is not enabled for provider 'prov'." in err  # mutant says "Would run"


def test_execute_would_run_without_yes(monkeypatch, tmp_path, capfd):
    # kills 152 (Would-run echo), 154/155 (Next text).
    providers = {"prov": _prov(exec_command=["true"])}
    code = _run_execute(monkeypatch, tmp_path, _payload(), providers=providers, yes=False)
    assert code == 2
    out = capfd.readouterr().out
    assert "Would run (provider prov): ['true']" in out
    assert "Next: re-run with --yes to execute." in out
    assert "XX" not in out


def test_execute_provider_runs_and_propagates_code(monkeypatch, tmp_path, capfd):
    # kills 158 (Running echo) and pins prompt substitution + exit-code propagation.
    script = "import sys; sys.stdout.write(sys.argv[1]); sys.exit(5)"
    providers = {"prov": _prov(exec_command=[sys.executable, "-c", script, "{prompt}"])}
    code = _run_execute(
        monkeypatch, tmp_path, _payload(prompt="PMARK"), providers=providers, yes=True
    )
    assert code == 5  # subprocess return code propagated
    cap = capfd.readouterr()
    assert "Running prov/m via provider 'prov'..." in cap.out
    assert "PMARK" in cap.out  # {prompt} substituted into the provider exec_command


def test_execute_provider_command_not_found(monkeypatch, tmp_path, capfd):
    # kills 163-176 (failure msgs, argv[0] vs argv[1], streams), 177 (Exit code).
    providers = {"prov": _prov(exec_command=["definitely-not-a-real-binary-xyz", "{prompt}"])}
    code = _run_execute(monkeypatch, tmp_path, _payload(), providers=providers, yes=True)
    assert code == 1  # EXIT_RUNTIME
    err = capfd.readouterr().err
    assert "Execution failed: command not found: definitely-not-a-real-binary-xyz" in err
    assert "Next: install the provider's CLI or fix exec_command." in err
    assert "XX" not in err


def _via_host_model():
    return _host_model(
        model_id="m",
        provider="prov",
        execution_targets=[
            ExecutionTarget(
                host="codex-cli",
                host_model_id="hm",
                command_template=[
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.write(sys.argv[1]); sys.exit(6)",
                    "{prompt}",
                ],
            )
        ],
    )


def test_execute_dispatches_to_host(monkeypatch, tmp_path, capfd):
    # kills 95 (prompt->None), 96 (yes->None): the host dispatch must forward the real
    # prompt and yes flag so an available host actually runs.
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    model = _via_host_model()
    er = {"command_preview": "codex hm", "host_model_id": "hm"}
    payload = _payload(
        recommendation={"model": model.key, "provider": "prov"}, execution_route=er, prompt="HMARK"
    )
    code = _run_execute(
        monkeypatch, tmp_path, payload, providers={}, models=[model], yes=True, dry_run=False
    )
    assert code == 6  # host command ran (yes forwarded) and propagated its code
    assert "HMARK" in capfd.readouterr().out  # prompt forwarded (mutant 95 -> None crashes)


def test_execute_incomplete_route_falls_back_to_provider(monkeypatch, tmp_path, capfd):
    # kills 85 (and->or): an execution_route missing command_preview must NOT dispatch
    # to the host; it falls through to the provider gate.
    er = {"command_preview": "", "host_model_id": "hm"}
    code = _run_execute(monkeypatch, tmp_path, _payload(execution_route=er), providers={})
    assert code == 2
    assert "Execution is not enabled for provider 'prov'." in capfd.readouterr().err


def test_execute_legacy_opt_in_requires_all_three(monkeypatch, tmp_path, capfd):
    # kills 76 (and->or in legacy_opt_in): a provider that is NOT fully opted in
    # (supports_execution False) must not shadow the host-dispatch path.
    monkeypatch.setattr(hosts_mod.shutil, "which", lambda c: f"/usr/bin/{c}")
    model = _via_host_model()
    er = {"command_preview": "codex hm", "host_model_id": "hm"}
    providers = {"prov": _prov(supports_execution=False, exec_command=["x"])}
    payload = _payload(
        recommendation={"model": model.key, "provider": "prov"}, execution_route=er, prompt="LMARK"
    )
    code = _run_execute(
        monkeypatch, tmp_path, payload, providers=providers, models=[model], yes=True
    )
    assert code == 6  # legacy_opt_in is False -> host dispatch runs (mutant 76 -> "not enabled")
