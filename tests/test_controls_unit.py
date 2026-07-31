"""Mutation-hardening for controls._reject_reason and apply_controls.

Each reject branch is exercised with its exact reason string, plus the
keep/None path and price/host boundaries, so flipped comparisons, swapped
set-membership, and mutated strings are all caught.
"""

from __future__ import annotations

from factories import make_model, make_target

from agentrouter.controls import RouteControls, _reject_reason, apply_controls
from agentrouter.schema import ReleaseChannel


def _reason(m, c):
    vendor_in = {v.lower() for v in c.vendor}
    vendor_out = {v.lower() for v in c.exclude_vendor}
    host_in = {h.lower() for h in c.host}
    host_out = {h.lower() for h in c.exclude_host}
    model_pin = c.model.lower() if c.model else None
    return _reject_reason(m, c, vendor_in, vendor_out, host_in, host_out, model_pin)


# --- _reject_reason: each branch, exact string --------------------------------


def test_no_controls_keeps_model_returns_none():
    assert _reason(make_model(), RouteControls()) is None


def test_vendor_in_mismatch_rejected():
    r = _reason(make_model(vendor="openai"), RouteControls(vendor=("anthropic",)))
    assert r is not None and "not in --vendor" in r


def test_vendor_in_match_kept():
    assert _reason(make_model(vendor="anthropic"), RouteControls(vendor=("anthropic",))) is None


def test_vendor_out_match_rejected():
    r = _reason(make_model(vendor="openai"), RouteControls(exclude_vendor=("openai",)))
    assert r == "vendor 'openai' excluded by --exclude-vendor"


def test_vendor_out_nonmatch_kept():
    m = make_model(vendor="anthropic")
    assert _reason(m, RouteControls(exclude_vendor=("openai",))) is None


def test_model_pin_mismatch_rejected():
    r = _reason(make_model(model_id="claude-x"), RouteControls(model="something-else"))
    assert r == "does not match --model something-else"


def test_model_pin_matches_bare_model_id_kept():
    m = make_model(provider="anthropic", model_id="claude-x")
    assert _reason(m, RouteControls(model="claude-x")) is None


def test_model_pin_matches_vendor_key_kept():
    m = make_model(vendor="anthropic", model_id="claude-x")
    assert _reason(m, RouteControls(model="anthropic/claude-x")) is None


def test_host_in_disjoint_rejected():
    m = make_model(execution_targets=[make_target(host="codex-cli")])
    r = _reason(m, RouteControls(host=("claude-code",)))
    assert r is not None and "no execution target on --host" in r


def test_host_in_present_kept():
    m = make_model(execution_targets=[make_target(host="claude-code")])
    assert _reason(m, RouteControls(host=("claude-code",))) is None


def test_host_out_present_rejected():
    m = make_model(execution_targets=[make_target(host="claude-code")])
    r = _reason(m, RouteControls(exclude_host=("claude-code",)))
    assert r == "execution host excluded by --exclude-host"


def test_host_out_absent_kept():
    m = make_model(execution_targets=[make_target(host="codex-cli")])
    assert _reason(m, RouteControls(exclude_host=("claude-code",))) is None


def test_stable_only_drops_preview():
    m = make_model(release_channel=ReleaseChannel.preview)
    r = _reason(m, RouteControls(stable_only=True))
    assert r is not None and "is not stable" in r


def test_stable_only_keeps_stable():
    m = make_model(release_channel=ReleaseChannel.stable)
    assert _reason(m, RouteControls(stable_only=True)) is None


def test_max_price_unknown_price_rejected():
    m = make_model(input_price_per_million=None)
    r = _reason(m, RouteControls(max_price=5.0))
    assert r is not None and "input price unknown" in r


def test_max_price_over_cap_rejected():
    m = make_model(input_price_per_million=10.0)
    r = _reason(m, RouteControls(max_price=5.0))
    assert r == "input price $10.0/1M > --max-price $5.0"


def test_max_price_equal_to_cap_kept():
    # boundary: price == cap must NOT be rejected (> not >=)
    m = make_model(input_price_per_million=5.0)
    assert _reason(m, RouteControls(max_price=5.0)) is None


def test_max_price_under_cap_kept():
    m = make_model(input_price_per_million=1.0)
    assert _reason(m, RouteControls(max_price=5.0)) is None


def test_prohibit_tool_supported_rejected():
    m = make_model(tool_support=["web_search"])
    r = _reason(m, RouteControls(prohibit_tool=("web_search",)))
    assert r is not None and "prohibited tool" in r


def test_prohibit_tool_not_supported_kept():
    m = make_model(tool_support=[])
    assert _reason(m, RouteControls(prohibit_tool=("web_search",))) is None


# --- apply_controls: partition, formatting, immutability ----------------------


def test_apply_controls_inactive_returns_copies_and_empty_dropped():
    models = [make_model(model_id="a"), make_model(model_id="b")]
    kept, dropped = apply_controls(models, RouteControls())
    assert kept == models
    assert kept is not models  # a new list, not the same object
    assert dropped == []


def test_apply_controls_partitions_kept_and_dropped():
    keep = make_model(vendor="anthropic", model_id="keep")
    drop = make_model(vendor="openai", model_id="drop")
    kept, dropped = apply_controls([keep, drop], RouteControls(vendor=("anthropic",)))
    assert [m.model_id for m in kept] == ["keep"]
    assert [d["model"] for d in dropped] == [drop.key]


def test_apply_controls_dropped_reason_prefixed_with_control():
    drop = make_model(vendor="openai")
    _, dropped = apply_controls([drop], RouteControls(vendor=("anthropic",)))
    assert len(dropped) == 1
    assert dropped[0]["reason"].startswith("control: ")


def test_apply_controls_does_not_mutate_input_list():
    models = [make_model(vendor="openai")]
    original = list(models)
    apply_controls(models, RouteControls(vendor=("anthropic",)))
    assert models == original
