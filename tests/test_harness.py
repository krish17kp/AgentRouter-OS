"""Introspective harness detection (Production Milestone 1).

Evidence-only: a named harness is reported only from the exact variable that
tool sets for itself; every other combination — including a bare interactive
shell and total silence — must stay generic/unknown rather than guess.
"""

from __future__ import annotations

from agentrouter import harness


def test_claudecode_env_var_is_detected():
    info = harness.detect_harness({"CLAUDECODE": "1"})
    assert info.name == harness.CLAUDE_CODE
    assert "CLAUDECODE" in info.evidence


def test_github_actions_is_detected():
    info = harness.detect_harness({"GITHUB_ACTIONS": "true", "CI": "true"})
    assert info.name == harness.CI_GITHUB_ACTIONS


def test_generic_ci_is_detected_when_not_github():
    info = harness.detect_harness({"CI": "true"})
    assert info.name == harness.CI_GENERIC


def test_github_actions_false_string_is_not_a_false_positive():
    """A literal 'false' string must not be treated as truthy evidence."""
    info = harness.detect_harness({"GITHUB_ACTIONS": "false", "CI": "false", "TERM": "xterm"})
    assert info.name == harness.GENERIC


def test_plain_terminal_is_generic_not_a_guessed_tool():
    info = harness.detect_harness({"TERM": "xterm-256color", "SHELL": "/bin/bash"})
    assert info.name == harness.GENERIC


def test_empty_environment_is_unknown():
    info = harness.detect_harness({})
    assert info.name == harness.UNKNOWN


def test_claudecode_wins_over_ci_when_both_present():
    """Claude Code can itself run inside CI; the more specific signal wins."""
    info = harness.detect_harness({"CLAUDECODE": "1", "CI": "true"})
    assert info.name == harness.CLAUDE_CODE


def test_unrelated_editor_variable_is_never_used_alone():
    """A weak, unrelated variable (e.g. an editor's own env var) must not name a harness."""
    info = harness.detect_harness({"SOME_UNRELATED_EDITOR_VAR": "1"})
    assert info.name in (harness.GENERIC, harness.UNKNOWN)
    assert info.name not in (harness.CLAUDE_CODE, harness.CI_GITHUB_ACTIONS, harness.CI_GENERIC)


def test_detect_harness_defaults_to_the_real_process_environment():
    """No env arg reads os.environ — this process runs under Claude Code, so it must be detected."""
    info = harness.detect_harness()
    assert info.name == harness.CLAUDE_CODE
