"""Mutation-hardening for agentrouter.hosts.

Detection is pinned per branch (CLI found/missing, API env set/unset, manual,
unknown), including exact reason strings; route resolution and the shared
execution-route block dict are pinned key-by-key. shutil.which and os.environ
are controlled so tests are hermetic and offline.
"""

from __future__ import annotations

from factories import make_model, make_target

from agentrouter import hosts
from agentrouter.hosts import (
    AVAILABLE,
    UNAVAILABLE,
    UNKNOWN,
    HostStatus,
    command_preview,
    detect_host,
    execution_route_block,
    known_hosts,
    resolve_execution_route,
    target_status,
)
from agentrouter.schema import ExecutionMode


def _which(found):
    """Return a fake shutil.which that reports every command found/absent."""
    return lambda cmd: f"/usr/bin/{cmd}" if found else None


# --- detect_host --------------------------------------------------------------


def test_manual_always_available():
    st = detect_host("manual")
    assert st.availability == AVAILABLE
    assert st.reason == "manual execution is always available"


def test_cli_host_found_on_path(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(True))
    st = detect_host("claude-code")
    assert st.availability == AVAILABLE
    assert st.reason == "'claude' found on PATH"


def test_cli_host_missing_from_path(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(False))
    st = detect_host("claude-code")
    assert st.availability == UNAVAILABLE
    assert st.reason == "'claude' not found on PATH"


def test_codex_cli_host_uses_its_own_command(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(True))
    st = detect_host("codex-cli")
    assert st.reason == "'codex' found on PATH"


def test_custom_host_with_required_command_uses_cli_path(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(True))
    st = detect_host("some-custom-host", required_command="mytool")
    assert st.availability == AVAILABLE
    assert st.reason == "'mytool' found on PATH"


def test_api_host_available_when_env_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    st = detect_host("anthropic-api")
    assert st.availability == AVAILABLE
    assert st.reason == "ANTHROPIC_API_KEY is set"
    assert "sk-secret" not in st.reason  # never leaks the value


def test_api_host_unavailable_when_env_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    st = detect_host("openai-api")
    assert st.availability == UNAVAILABLE
    assert st.reason == "OPENAI_API_KEY is not set"


def test_api_host_ignores_required_command(monkeypatch):
    # required_command must NOT flip an API host onto the CLI branch.
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    monkeypatch.setattr(hosts.shutil, "which", _which(False))
    st = detect_host("gemini-api", required_command="anything")
    assert st.availability == AVAILABLE
    assert st.reason == "GOOGLE_API_KEY is set"


def test_unknown_host_is_unknown():
    st = detect_host("mystery-host")
    assert st.availability == UNKNOWN
    assert st.reason == "unrecognized host; cannot verify availability"


def test_target_status_delegates_to_detect_host(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(True))
    t = make_target(host="claude-code", required_command="claude")
    st = target_status(t)
    assert st.host == "claude-code"
    assert st.availability == AVAILABLE


# --- command_preview ----------------------------------------------------------


def test_command_preview_no_template():
    t = make_target(host="anthropic-api", execution_mode=ExecutionMode.api, command_template=None)
    assert command_preview(t) == "(no command - api host 'anthropic-api')"


def test_command_preview_redacts_prompt_by_default():
    t = make_target(command_template=["claude", "-p", "{prompt}"])
    assert command_preview(t) == "claude -p <prompt redacted>"


def test_command_preview_unredacted_keeps_prompt():
    t = make_target(command_template=["claude", "-p", "{prompt}"])
    assert command_preview(t, redact=False) == "claude -p {prompt}"


def test_command_preview_leaves_non_prompt_args_intact():
    t = make_target(command_template=["claude", "--model", "x", "{prompt}"])
    assert command_preview(t) == "claude --model x <prompt redacted>"


# --- resolve_execution_route --------------------------------------------------


def test_resolve_picks_first_available(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(True))
    m = make_model(
        execution_targets=[
            make_target(host="claude-code", required_command="claude"),
            make_target(host="codex-cli", required_command="codex"),
        ]
    )
    route = resolve_execution_route(m)
    assert route.target.host == "claude-code"
    assert route.is_available is True
    assert len(route.all_statuses) == 2


def test_resolve_skips_unavailable_to_reach_available(monkeypatch):
    # first target's command is absent, second present
    monkeypatch.setattr(
        hosts, "target_status", lambda t: HostStatus(
            t.host, AVAILABLE if t.host == "codex-cli" else UNAVAILABLE, "test"
        )
    )
    m = make_model(
        execution_targets=[make_target(host="claude-code"), make_target(host="codex-cli")]
    )
    route = resolve_execution_route(m)
    assert route.target.host == "codex-cli"
    assert route.is_available is True


def test_resolve_none_available_without_include_returns_no_target(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(False))
    m = make_model(execution_targets=[make_target(host="claude-code", required_command="claude")])
    route = resolve_execution_route(m, include_unavailable=False)
    assert route.target is None
    assert route.status is not None  # the "global best" status is still surfaced
    assert route.is_available is False


def test_resolve_none_available_with_include_returns_first_target(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(False))
    first = make_target(host="claude-code", required_command="claude")
    m = make_model(execution_targets=[first])
    route = resolve_execution_route(m, include_unavailable=True)
    assert route.target is first
    assert route.is_available is False


def test_resolve_no_targets_all_none():
    route = resolve_execution_route(make_model(execution_targets=[]))
    assert route.target is None
    assert route.status is None
    assert route.all_statuses == []


# --- execution_route_block ----------------------------------------------------


def test_route_block_none_row_returns_none():
    assert execution_route_block(None, {}) is None


def test_route_block_unknown_model_returns_none():
    assert execution_route_block({"model": "missing"}, {}) is None


def test_route_block_model_without_targets_returns_none():
    m = make_model(model_id="notargets", execution_targets=[])
    assert execution_route_block({"model": m.key}, {m.key: m}) is None


def test_route_block_full_payload(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(True))
    t = make_target(
        host="claude-code",
        host_model_id="claude-code-id",
        command_template=["claude", "-p", "{prompt}"],
        required_command="claude",
        required_env=["ANTHROPIC_API_KEY"],
    )
    m = make_model(
        provider="anthropic",
        vendor="anthropic",
        model_id="claude-x",
        display_name="Claude X",
        context_window=200_000,
        max_output_tokens=8_192,
        execution_targets=[t],
    )
    block = execution_route_block({"model": m.key}, {m.key: m})
    assert block["vendor"] == "anthropic"
    assert block["model_id"] == "claude-x"
    assert block["display_name"] == "Claude X"
    assert block["release_channel"] == "stable"
    assert block["host"] == "claude-code"
    assert block["host_model_id"] == "claude-code-id"
    assert block["execution_mode"] == "cli"
    assert block["availability"] == "available"
    assert block["availability_reason"] == "'claude' found on PATH"
    assert block["command_preview"] == "claude -p <prompt redacted>"
    assert block["required_env"] == ["ANTHROPIC_API_KEY"]
    assert block["context_window"] == 200_000
    assert block["max_output_tokens"] == 8_192
    assert block["all_hosts"] == [{"host": "claude-code", "availability": "available"}]


def test_route_block_reports_unavailable_host(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", _which(False))
    t = make_target(host="claude-code", required_command="claude", command_template=["claude"])
    m = make_model(model_id="claude-x", execution_targets=[t])
    block = execution_route_block({"model": m.key}, {m.key: m})
    assert block["host"] == "claude-code"  # include_unavailable surfaces it
    assert block["availability"] == "unavailable"


# --- known_hosts --------------------------------------------------------------


def test_known_hosts_lists_all_cli_api_and_manual():
    ks = known_hosts()
    assert "claude-code" in ks
    assert "codex-cli" in ks
    assert "anthropic-api" in ks
    assert "openrouter" in ks
    assert ks[-1] == "manual"
    assert len(ks) == 7
