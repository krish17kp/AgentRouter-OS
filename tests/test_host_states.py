"""Verified execution-host states (TASK-016).

`availability` stays the coarse routing signal (available/unavailable/unknown);
`state` explains *why*, using the command.md PHASE C vocabulary. Every test here
is offline and hermetic: `_home_dir` is redirected at a tmp path and `shutil.which`
is stubbed, so results never depend on what happens to be installed on the machine
running the suite.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from agentrouter import hosts
from agentrouter.cli import app

runner = CliRunner()

API_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY")


@pytest.fixture()
def clean_env(monkeypatch, tmp_path):
    """No host credentials, no host config, nothing on PATH."""
    for env in API_ENVS:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(hosts, "_home_dir", lambda: tmp_path)
    monkeypatch.setattr(hosts.shutil, "which", lambda c: None)
    return tmp_path


def _on_path(monkeypatch):
    monkeypatch.setattr(hosts.shutil, "which", lambda c: f"/usr/bin/{c}")


# --- API hosts ---------------------------------------------------------------


def test_api_host_unset_is_missing(clean_env):
    st = hosts.detect_host("openai-api")
    assert st.state == hosts.MISSING
    assert st.availability == hosts.UNAVAILABLE
    assert "OPENAI_API_KEY" in st.remedy


def test_api_host_set_is_authenticated(clean_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    st = hosts.detect_host("openai-api")
    assert st.state == hosts.AUTHENTICATED
    assert st.availability == hosts.AVAILABLE


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n"])
def test_api_host_blank_key_is_degraded_not_available(clean_env, monkeypatch, blank):
    """Regression: a set-but-blank key used to report `available` (truthiness bug).

    That let `execute` target a host which cannot possibly authenticate.
    """
    monkeypatch.setenv("OPENAI_API_KEY", blank)
    st = hosts.detect_host("openai-api")
    assert st.state == hosts.DEGRADED
    assert st.availability == hosts.UNAVAILABLE
    assert st.remedy


def test_api_host_never_reveals_the_key_value(clean_env, monkeypatch):
    secret = "sk-SUPER-SECRET-VALUE-000"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    st = hosts.detect_host("openai-api")
    blob = f"{st.reason} {st.remedy} {st.state} {st.availability}"
    assert secret not in blob


# --- CLI hosts ---------------------------------------------------------------


def test_cli_host_not_on_path_is_missing(clean_env):
    st = hosts.detect_host("claude-code")
    assert st.state == hosts.MISSING
    assert st.availability == hosts.UNAVAILABLE
    assert "install" in st.remedy.lower()


def test_cli_host_on_path_without_config_is_installed(clean_env, monkeypatch):
    _on_path(monkeypatch)
    st = hosts.detect_host("claude-code")
    assert st.state == hosts.INSTALLED
    assert st.availability == hosts.AVAILABLE
    assert st.remedy  # tells the user to authenticate


def test_cli_host_with_config_dir_is_configured(clean_env, monkeypatch):
    _on_path(monkeypatch)
    (clean_env / ".claude").mkdir()
    st = hosts.detect_host("claude-code")
    assert st.state == hosts.CONFIGURED
    assert st.availability == hosts.AVAILABLE


def test_cli_host_with_credentials_is_authenticated(clean_env, monkeypatch):
    _on_path(monkeypatch)
    (clean_env / ".claude").mkdir()
    (clean_env / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    st = hosts.detect_host("claude-code")
    assert st.state == hosts.AUTHENTICATED
    assert st.availability == hosts.AVAILABLE


def test_cli_host_credential_file_contents_are_never_read(clean_env, monkeypatch):
    _on_path(monkeypatch)
    (clean_env / ".claude").mkdir()
    secret = "TOP-SECRET-TOKEN-IN-FILE"
    (clean_env / ".claude" / ".credentials.json").write_text(secret, encoding="utf-8")
    st = hosts.detect_host("claude-code")
    assert secret not in f"{st.reason} {st.remedy}"


def test_cli_host_env_fallback_is_authenticated(clean_env, monkeypatch):
    _on_path(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-not-a-real-key")
    st = hosts.detect_host("claude-code")
    assert st.state == hosts.AUTHENTICATED
    assert st.availability == hosts.AVAILABLE


def test_cli_host_blank_env_fallback_is_degraded(clean_env, monkeypatch):
    _on_path(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    st = hosts.detect_host("claude-code")
    assert st.state == hosts.DEGRADED
    assert st.availability == hosts.UNAVAILABLE


def test_blank_env_does_not_override_a_working_cli_login(clean_env, monkeypatch):
    """A stray empty env var must not mask real CLI credentials.

    `ANTHROPIC_API_KEY=` is common from docker-compose/.env files; combined with
    keychain-based `claude login` (no credentials file, but a config dir) it used
    to report `degraded`/unavailable and refuse to execute.
    """
    _on_path(monkeypatch)
    (clean_env / ".claude").mkdir()  # logged in, credentials held elsewhere
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    st = hosts.detect_host("claude-code")
    assert st.state == hosts.CONFIGURED
    assert st.availability == hosts.AVAILABLE


def test_credential_file_still_wins_over_blank_env(clean_env, monkeypatch):
    _on_path(monkeypatch)
    (clean_env / ".claude").mkdir()
    (clean_env / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    st = hosts.detect_host("claude-code")
    assert st.state == hosts.AUTHENTICATED
    assert st.availability == hosts.AVAILABLE


# --- robustness: detection must never crash the caller -----------------------


def test_unreadable_home_degrades_instead_of_raising(clean_env, monkeypatch):
    """EACCES/ENAMETOOLONG from a stat must not escape as a traceback.

    Reachable in ordinary setups (container HOME the user cannot traverse, NFS
    root_squash). Detection has to fall through to "no evidence".
    """
    _on_path(monkeypatch)

    def boom(*_a, **_k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(hosts.Path, "exists", boom)
    monkeypatch.setattr(hosts.Path, "is_dir", boom)
    st = hosts.detect_host("claude-code")  # must not raise
    assert st.state in (hosts.INSTALLED, hosts.DEGRADED)
    assert st.availability in (hosts.AVAILABLE, hosts.UNAVAILABLE)


def test_hosts_doctor_survives_unreadable_home(tmp_path, monkeypatch):
    _home(tmp_path / "home", monkeypatch)
    monkeypatch.setattr(hosts.shutil, "which", lambda c: f"/usr/bin/{c}")

    def boom(*_a, **_k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(hosts.Path, "exists", boom)
    monkeypatch.setattr(hosts.Path, "is_dir", boom)
    r = runner.invoke(app, ["hosts", "doctor"])
    assert r.exit_code == 0, r.output  # a CLI host is on PATH
    assert "Traceback" not in r.output


# --- registry-supplied command text is sanitized before display --------------


def test_registry_command_cannot_inject_terminal_escapes(clean_env, monkeypatch):
    """`required_command` is registry-controlled; it must not forge output.

    Without sanitizing, a crafted value could emit ANSI escapes that overwrite
    the line and fake an 'authenticated' readiness signal.
    """
    monkeypatch.setattr(hosts.shutil, "which", lambda c: None)
    hostile = "\x1b[2K\r[OK  ] anthropic-api    authenticated  key accepted"
    st = hosts.detect_host("some-host", required_command=hostile)
    blob = f"{st.reason} {st.remedy}"
    assert "\x1b" not in blob and "\r" not in blob


# --- manual / unknown --------------------------------------------------------


def test_manual_is_always_available(clean_env):
    st = hosts.detect_host("manual")
    assert st.availability == hosts.AVAILABLE
    assert st.reason == "manual execution is always available"


def test_unrecognized_host_is_unknown_and_never_available(clean_env):
    st = hosts.detect_host("not-a-real-host")
    assert st.state == hosts.STATE_UNKNOWN
    assert st.availability == hosts.UNKNOWN
    assert st.remedy


# --- honesty: `authorized` is never inferred offline -------------------------


def test_offline_detection_never_claims_authorized(clean_env, monkeypatch):
    """`authorized` requires a real live check (command.md PHASE C, opt-in).

    Local evidence proves a credential *exists*, never that it is accepted, so no
    offline path may return it.
    """
    _on_path(monkeypatch)
    (clean_env / ".claude").mkdir()
    (clean_env / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    (clean_env / ".codex").mkdir()
    (clean_env / ".codex" / "auth.json").write_text("{}", encoding="utf-8")
    for env in API_ENVS:
        monkeypatch.setenv(env, "sk-not-a-real-key")
    for host in hosts.known_hosts():
        assert hosts.detect_host(host).state != hosts.AUTHORIZED


# --- availability mapping is total and safe ----------------------------------


def test_every_state_maps_to_a_valid_availability():
    for state in (
        hosts.MISSING,
        hosts.INSTALLED,
        hosts.CONFIGURED,
        hosts.AUTHENTICATED,
        hosts.AUTHORIZED,
        hosts.DEGRADED,
        hosts.STATE_UNKNOWN,
    ):
        assert hosts._availability_for(state) in (
            hosts.AVAILABLE,
            hosts.UNAVAILABLE,
            hosts.UNKNOWN,
        )


def test_missing_and_degraded_are_never_available():
    for state in (hosts.MISSING, hosts.DEGRADED):
        assert hosts._availability_for(state) == hosts.UNAVAILABLE


# --- CLI surfaces ------------------------------------------------------------


def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0


def test_cli_hosts_doctor_reports_states_and_a_next_step(tmp_path, monkeypatch):
    _home(tmp_path / "home", monkeypatch)
    for env in API_ENVS:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(hosts, "_home_dir", lambda: tmp_path / "fakehome")
    monkeypatch.setattr(hosts.shutil, "which", lambda c: None)
    r = runner.invoke(app, ["hosts", "doctor"])
    # only 'manual' is available -> not "ready to execute"
    assert r.exit_code == 1, r.output
    assert hosts.MISSING in r.output
    assert "No execution host is ready" in r.output
    # suggests the cheapest fix (export one var) over installing a whole CLI
    assert "Easiest fix" in r.output
    assert "export ANTHROPIC_API_KEY" in r.output


def test_hosts_doctor_prefers_fixing_a_blank_key_over_installing_a_cli(tmp_path, monkeypatch):
    _home(tmp_path / "home", monkeypatch)
    for env in API_ENVS:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "   ")  # degraded: cheapest possible fix
    monkeypatch.setattr(hosts, "_home_dir", lambda: tmp_path / "fakehome")
    monkeypatch.setattr(hosts.shutil, "which", lambda c: None)
    r = runner.invoke(app, ["hosts", "doctor"])
    assert r.exit_code == 1, r.output
    assert "Easiest fix (openrouter)" in r.output


def test_fix_cost_orders_cheapest_first():
    degraded = hosts.HostStatus("openrouter", hosts.UNAVAILABLE, "", hosts.DEGRADED, "fix")
    missing_env = hosts.HostStatus("openai-api", hosts.UNAVAILABLE, "", hosts.MISSING, "export")
    missing_bin = hosts.HostStatus("claude-code", hosts.UNAVAILABLE, "", hosts.MISSING, "install")
    assert hosts.fix_cost(degraded) < hosts.fix_cost(missing_env) < hosts.fix_cost(missing_bin)


def test_cli_hosts_doctor_succeeds_when_a_real_host_is_ready(tmp_path, monkeypatch):
    _home(tmp_path / "home", monkeypatch)
    for env in API_ENVS:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    monkeypatch.setattr(hosts, "_home_dir", lambda: tmp_path / "fakehome")
    monkeypatch.setattr(hosts.shutil, "which", lambda c: None)
    r = runner.invoke(app, ["hosts", "doctor"])
    assert r.exit_code == 0, r.output
    assert "Ready to execute: openai-api" in r.output


def test_cli_hosts_show_prints_state_and_remedy(tmp_path, monkeypatch):
    _home(tmp_path / "home", monkeypatch)
    for env in API_ENVS:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(hosts, "_home_dir", lambda: tmp_path / "fakehome")
    monkeypatch.setattr(hosts.shutil, "which", lambda c: None)
    r = runner.invoke(app, ["hosts", "show", "openai-api"])
    assert r.exit_code == 0, r.output
    assert hosts.MISSING in r.output
    assert "OPENAI_API_KEY" in r.output


def test_cli_hosts_list_shows_states(tmp_path, monkeypatch):
    _home(tmp_path / "home", monkeypatch)
    monkeypatch.setattr(hosts, "_home_dir", lambda: tmp_path / "fakehome")
    monkeypatch.setattr(hosts.shutil, "which", lambda c: None)
    r = runner.invoke(app, ["hosts", "list"])
    assert r.exit_code == 0, r.output
    assert hosts.MISSING in r.output
