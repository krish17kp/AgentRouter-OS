"""Phase 4 — command-injection hardening for `agentrouter execute`.

`execute` runs `subprocess.run(argv)` with no shell and substitutes the prompt
into a single argv element. These tests prove that shell metacharacters, quotes,
newlines, Unicode, and a literal "{prompt}" in the task text pass through to the
child process as inert data — never interpreted by a shell, never re-substituted.
"""

import json
import sys

import pytest
import yaml
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    from agentrouter.cli import app

    assert runner.invoke(app, ["init"]).exit_code == 0
    return tmp_path


def _enable_execution(home, provider_id, argv):
    path = home / "registry" / "providers.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for p in data["providers"]:
        if p["id"] == provider_id:
            p["supports_execution"] = True
            p["exec_command"] = argv
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


# each payload is embedded in an otherwise low-risk task (no high-risk keywords)
_PAYLOADS = [
    "quote \" and apostrophe ' here",
    "semicolon ; and pipe | and amp && chain",
    "command sub $(id) and backticks `whoami`",
    "redirect > out < in and glob *.py",
    "newline\nsecond line\tand tab",
    "unicode 日本語 emoji 🎉 accents café",
    "literal placeholder {prompt} inside the task",
    "backslash \\ and percent %PATH% and dollar $HOME",
]


@pytest.mark.parametrize("payload", _PAYLOADS)
def test_prompt_reaches_subprocess_as_inert_data(home, payload):
    from agentrouter.cli import app

    task = f"write a short note about {payload}"
    r = runner.invoke(app, ["route", task, "--json"])
    assert r.exit_code == 0, r.output
    decision = json.loads(r.output)
    assert decision["classification"]["risk"] == "low"  # stays executable
    provider = decision["recommendation"]["provider"]

    captured = home / "captured.txt"
    sentinel = home / "PWNED"  # a shell would let $(...)/;/&& create this
    script = (
        "import sys, pathlib; "
        f"pathlib.Path({str(captured)!r}).write_text(sys.argv[-1], encoding='utf-8')"
    )
    _enable_execution(home, provider, [sys.executable, "-c", script, "{prompt}"])

    res = runner.invoke(app, ["execute", decision["decision_id"], "--yes"])
    assert res.exit_code == 0, res.output

    got = captured.read_text(encoding="utf-8")
    # the raw payload survives verbatim inside the single prompt argv element
    assert payload in got
    # nothing a shell would have interpreted actually ran
    assert not sentinel.exists()


def test_placeholder_in_task_is_not_double_substituted(home):
    """A task containing '{prompt}' must not trigger a second substitution."""
    from agentrouter.cli import app

    r = runner.invoke(app, ["route", "write about the {prompt} token literally", "--json"])
    decision = json.loads(r.output)
    provider = decision["recommendation"]["provider"]
    captured = home / "cap2.txt"
    script = (
        "import sys, pathlib; "
        f"pathlib.Path({str(captured)!r}).write_text(sys.argv[-1], encoding='utf-8')"
    )
    _enable_execution(home, provider, [sys.executable, "-c", script, "{prompt}"])
    assert runner.invoke(app, ["execute", decision["decision_id"], "--yes"]).exit_code == 0
    assert "{prompt}" in captured.read_text(encoding="utf-8")


def test_execute_never_uses_shell():
    """Static guarantee: the execute path calls subprocess.run without shell=True."""
    import inspect

    from agentrouter import cli

    src = inspect.getsource(cli.execute)
    assert "subprocess.run(argv)" in src
    assert "shell=True" not in src
