"""Hermetic OpenAI API and CLI execution gates; no paid requests."""

from __future__ import annotations

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest
import typer
import yaml
from typer.testing import CliRunner

from agentrouter import hosts, openai_adapter, store
from agentrouter import registry as registry_module
from agentrouter.cli import app

runner = CliRunner()


class _FrozenDate(date):
    @classmethod
    def today(cls):
        return date(2026, 7, 14)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-live")
    monkeypatch.setattr(registry_module, "date", _FrozenDate)
    real_detect = hosts.detect_host

    def detect(host, required_command=None):
        if host == "codex-cli":
            return hosts.HostStatus(host, hosts.UNAVAILABLE, "test: unavailable", hosts.MISSING)
        return real_detect(host, required_command)

    monkeypatch.setattr(hosts, "detect_host", detect)
    initialized = runner.invoke(app, ["init"])
    assert initialized.exit_code == 0, initialized.output
    return tmp_path


def _route(task="write a short haiku about routers"):
    result = runner.invoke(
        app,
        ["route", task, "--model", "openai/gpt-5.6-terra", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["execution_route"]["host"] == "openai-api"
    return payload


def _enable_openai(home):
    path = home / "registry" / "providers.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    next(p for p in data["providers"] if p["id"] == "openai")["supports_execution"] = True
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_api_execution_requires_provider_opt_in(home, monkeypatch):
    payload = _route()
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 2
    assert result.stderr.endswith(
        "OpenAI API execution is disabled for this provider.\n"
        "Set supports_execution: true for openai in providers.yaml to opt in.\n"
    )


def test_api_dry_run_never_calls_provider(home, monkeypatch):
    payload = _route()
    _enable_openai(home)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"], "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run" in result.output


def test_api_execution_requires_yes(home, monkeypatch):
    payload = _route()
    _enable_openai(home)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"]])
    assert result.exit_code == 2
    assert result.stdout.endswith("Next: re-run with --yes to submit this prompt to OpenAI.\n")


def test_api_execution_requires_nonblank_key(home, monkeypatch):
    payload = _route()
    _enable_openai(home)
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 2
    assert (
        "Execution target changed since this decision was recorded; route again." in result.stderr
    )


def test_api_error_is_reported_without_prompt_or_key(home, monkeypatch):
    payload = _route()
    _enable_openai(home)

    def fail(*_args, **_kwargs):
        raise openai_adapter.OpenAIAdapterError("OpenAI request failed with HTTP 429")

    monkeypatch.setattr(openai_adapter, "run_text_response", fail)
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 1
    assert "Execution failed: OpenAI request failed with HTTP 429" in result.stderr
    assert "test-key-not-live" not in result.output
    assert payload["prompt"] not in result.output


def test_api_execution_uses_exact_routed_model_and_prompt(home, monkeypatch):
    payload = _route()
    _enable_openai(home)
    calls = []

    def fake_response(model_id, prompt, api_key, *, max_output_tokens):
        calls.append((model_id, prompt, api_key, max_output_tokens))
        return "OpenAI response"

    monkeypatch.setattr(openai_adapter, "run_text_response", fake_response)
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 0, result.output
    assert "OpenAI response" in result.output
    assert calls == [
        (
            payload["execution_route"]["host_model_id"],
            payload["prompt"],
            "test-key-not-live",
            payload["execution_route"]["max_output_tokens"],
        )
    ]
    assert "test-key-not-live" not in result.output


def test_high_risk_api_execution_stays_blocked(home, monkeypatch):
    payload = _route("rotate the production auth credentials and deploy")
    _enable_openai(home)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 2
    assert "Execution blocked for" in result.stderr


def test_recorded_safety_gate_cannot_override_high_risk(home, monkeypatch):
    payload = _route("rotate the production auth credentials and deploy")
    payload["gates"]["auto_execute_allowed"] = True
    _enable_openai(home)
    monkeypatch.setattr(store, "load_decision", lambda *_args: payload)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 2
    assert "Execution blocked: stored safety gate changed; route again." in result.stderr


def test_invalid_stored_classification_is_rejected_before_dispatch(home, monkeypatch):
    payload = _route()
    payload["classification"] = {"risk": "low"}
    _enable_openai(home)
    monkeypatch.setattr(store, "load_decision", lambda *_args: payload)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 2
    assert result.stderr == "Execution blocked: stored classification is invalid; route again.\n"


def test_stored_approval_level_mismatch_is_rejected(home, monkeypatch):
    payload = _route()
    payload["gates"]["approval_level"] = "notify"
    _enable_openai(home)
    monkeypatch.setattr(store, "load_decision", lambda *_args: payload)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 2
    assert result.stderr == "Execution blocked: stored safety gate changed; route again.\n"


def test_tool_requiring_task_cannot_use_text_only_api(home, monkeypatch):
    payload = _route("Build a Python CLI and run tests")
    assert payload["classification"]["tool_needs"]
    _enable_openai(home)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 2
    assert result.stderr.endswith(
        "OpenAI API text execution requires a task with no external tools.\n"
    )


@pytest.mark.parametrize("field", ["host", "host_model_id", "model_id", "vendor"])
def test_api_execution_rejects_changed_recorded_target(home, monkeypatch, capfd, field):
    from agentrouter.cli import _execute_via_host

    payload = _route()
    _enable_openai(home)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    altered = {**payload["execution_route"], field: "changed"}
    with pytest.raises(typer.Exit) as error:
        _execute_via_host(
            payload["recommendation"],
            altered,
            payload["prompt"],
            yes=True,
            dry_run=False,
            classification=payload["classification"],
        )
    assert error.value.exit_code == 2
    assert capfd.readouterr().err == (
        "Execution target changed since this decision was recorded; route again.\n"
    )


@pytest.mark.parametrize("field", ["vendor", "provider"])
def test_api_execution_rejects_non_openai_model(home, monkeypatch, capfd, field):
    from agentrouter import cli

    payload = _route()
    providers, models = cli._load_registries()
    original = next(model for model in models if model.key == payload["recommendation"]["model"])
    changed = original.model_copy(update={field: "other"})
    monkeypatch.setattr(cli, "_load_registries", lambda: (providers, [changed]))
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    with pytest.raises(typer.Exit) as error:
        cli._execute_via_host(
            {"model": changed.key},
            {},
            payload["prompt"],
            yes=True,
            dry_run=False,
            classification=payload["classification"],
        )
    assert error.value.exit_code == 2
    assert capfd.readouterr().err == "OpenAI API target is not attached to an OpenAI model.\n"


def test_api_execution_rechecks_host_readiness(home, monkeypatch, capfd):
    from agentrouter import cli

    payload = _route()
    _enable_openai(home)
    real_resolve = hosts.resolve_execution_route

    def unavailable(model, include_unavailable=False):
        resolved = real_resolve(model, include_unavailable=include_unavailable)
        status = hosts.HostStatus(
            "openai-api", hosts.UNAVAILABLE, "test: unavailable", hosts.MISSING
        )
        return hosts.ResolvedRoute(resolved.target, status, [status])

    monkeypatch.setattr(hosts, "resolve_execution_route", unavailable)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    with pytest.raises(typer.Exit) as error:
        cli._execute_via_host(
            payload["recommendation"],
            payload["execution_route"],
            payload["prompt"],
            yes=True,
            dry_run=False,
            classification=payload["classification"],
        )
    assert error.value.exit_code == 2
    assert capfd.readouterr().err == (
        "Not enabled: host 'openai-api' is missing (test: unavailable).\n"
    )


def test_api_execution_rechecks_key_before_dispatch(home, monkeypatch, capfd):
    from agentrouter import cli

    payload = _route()
    _enable_openai(home)
    monkeypatch.delenv("OPENAI_API_KEY")

    def ready(model, include_unavailable=False):
        target = next(t for t in model.execution_targets if t.host == "openai-api")
        status = hosts.HostStatus("openai-api", hosts.AVAILABLE, "test: ready", hosts.AUTHENTICATED)
        return hosts.ResolvedRoute(target, status, [status])

    monkeypatch.setattr(hosts, "resolve_execution_route", ready)
    monkeypatch.setattr(openai_adapter, "run_text_response", lambda *a, **kw: pytest.fail("called"))
    with pytest.raises(typer.Exit) as error:
        cli._execute_via_host(
            payload["recommendation"],
            payload["execution_route"],
            payload["prompt"],
            yes=True,
            dry_run=False,
            classification=payload["classification"],
        )
    assert error.value.exit_code == 2
    assert capfd.readouterr().err == "OpenAI API key is no longer available; route again.\n"


def test_api_execution_sanitizes_provider_output(home, monkeypatch):
    payload = _route()
    _enable_openai(home)
    monkeypatch.setattr(
        openai_adapter, "run_text_response", lambda *a, **kw: "Hello\nWorld\t!\x1b[31m"
    )
    result = runner.invoke(app, ["execute", payload["decision_id"], "--yes"])
    assert result.exit_code == 0
    assert "Running " in result.stdout
    assert result.stdout.endswith("Hello\nWorld\t!?[31m\n")
    assert "\x1b" not in result.stdout


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return json.dumps(self.payload).encode()


def test_response_request_is_private_bounded_and_text_only(monkeypatch):
    seen = []

    def fake_open(request, *, timeout):
        seen.append((request, timeout))
        return _Response(
            {
                "status": "completed",
                "output": [
                    {"type": "reasoning", "summary": []},
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Hello"}],
                    },
                ],
            }
        )

    monkeypatch.setattr(openai_adapter, "urlopen", fake_open)
    assert (
        openai_adapter.run_text_response("model-id", "prompt", "secret", max_output_tokens=99999)
        == "Hello"
    )
    request, timeout = seen[0]
    assert timeout == openai_adapter.TIMEOUT_SECONDS
    assert request.full_url == openai_adapter.RESPONSES_URL
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.get_header("Content-type") == "application/json"
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {
        "model": "model-id",
        "input": "prompt",
        "max_output_tokens": openai_adapter.MAX_OUTPUT_TOKENS,
        "store": False,
        "stream": False,
    }


def test_openai_request_does_not_follow_redirects_or_forward_credentials():
    class RedirectHandler(BaseHTTPRequestHandler):
        visited = []

        def do_POST(self):
            self.visited.append(self.path)
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/capture")
            self.end_headers()

        def do_GET(self):
            self.visited.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/responses",
            data=b"{}",
            headers={"Authorization": "Bearer fixture-secret"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            openai_adapter._open_url(request, timeout=2)
        assert error.value.code == 302
        assert RedirectHandler.visited == ["/responses"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_response_collects_only_assistant_text(monkeypatch):
    payload = {
        "status": "completed",
        "output": [
            "ignored",
            {"type": "reasoning", "content": [{"type": "output_text", "text": "private"}]},
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "output_text", "text": "input"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [None, {"type": "output_text", "text": "one"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "two"}],
            },
        ],
    }
    monkeypatch.setattr(openai_adapter, "urlopen", lambda *_args, **_kw: _Response(payload))
    assert (
        openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=10)
        == "one\ntwo"
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "OpenAI response did not complete"),
        ({"status": "completed"}, "OpenAI response had no output items"),
        ({"status": "completed", "output": "not a list"}, "OpenAI response had no output items"),
        (
            {
                "status": "completed",
                "output": [None, {"type": "message", "role": "assistant", "content": "not a list"}],
            },
            "OpenAI response contained no text output",
        ),
        (
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": 123}],
                    }
                ],
            },
            "OpenAI response contained no text output",
        ),
    ],
)
def test_malformed_response_items_are_rejected(monkeypatch, payload, message):
    monkeypatch.setattr(openai_adapter, "urlopen", lambda *_args, **_kw: _Response(payload))
    with pytest.raises(openai_adapter.OpenAIAdapterError) as error:
        openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=10)
    assert str(error.value) == message


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"status": "incomplete", "output": []}, "OpenAI response did not complete"),
        ({"status": "completed", "output": []}, "OpenAI response contained no text output"),
        (
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "refusal", "refusal": "no"}],
                    }
                ],
            },
            "OpenAI refused this request",
        ),
        (
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "   "}],
                    }
                ],
            },
            "OpenAI response contained no text output",
        ),
    ],
)
def test_response_rejects_non_text_or_incomplete_results(monkeypatch, payload, message):
    monkeypatch.setattr(openai_adapter, "urlopen", lambda *_args, **_kw: _Response(payload))
    with pytest.raises(openai_adapter.OpenAIAdapterError) as error:
        openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=10)
    assert str(error.value) == message


@pytest.mark.parametrize(
    "failure",
    [
        HTTPError(openai_adapter.RESPONSES_URL, 429, "secret-rate-limit", {}, None),
        URLError("secret-network-failure"),
        TimeoutError("secret-timeout"),
    ],
)
def test_network_errors_do_not_expose_secrets(monkeypatch, failure):
    def fail_open(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(openai_adapter, "urlopen", fail_open)
    with pytest.raises(openai_adapter.OpenAIAdapterError) as error:
        openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=10)
    assert "secret" not in str(error.value)
    if isinstance(failure, HTTPError):
        assert str(error.value) == "OpenAI request failed with HTTP 429"
    else:
        assert str(error.value) == "OpenAI request failed or timed out"


def test_response_size_and_json_are_bounded(monkeypatch):
    class _RawResponse(_Response):
        def read(self, _limit):
            return b"not json and too large"

    monkeypatch.setattr(openai_adapter, "urlopen", lambda *_args, **_kw: _RawResponse({}))
    monkeypatch.setattr(openai_adapter, "MAX_RESPONSE_BYTES", 8)
    with pytest.raises(openai_adapter.OpenAIAdapterError) as error:
        openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=10)
    assert str(error.value) == "OpenAI response exceeded the size limit"
    monkeypatch.setattr(openai_adapter, "MAX_RESPONSE_BYTES", 200)
    with pytest.raises(openai_adapter.OpenAIAdapterError) as error:
        openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=10)
    assert str(error.value) == "OpenAI returned invalid JSON"


def test_response_reads_one_byte_past_the_limit(monkeypatch):
    class _BoundedResponse(_Response):
        def read(self, limit):
            assert limit == 9
            return b"123456789"[:limit]

    monkeypatch.setattr(openai_adapter, "urlopen", lambda *_args, **_kw: _BoundedResponse({}))
    monkeypatch.setattr(openai_adapter, "MAX_RESPONSE_BYTES", 8)
    with pytest.raises(openai_adapter.OpenAIAdapterError) as error:
        openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=10)
    assert str(error.value) == "OpenAI response exceeded the size limit"


def test_response_at_exact_size_limit_reaches_json_parser(monkeypatch):
    class _ExactResponse(_Response):
        def read(self, limit):
            assert limit == 9
            return b"invalid!"[:limit]

    monkeypatch.setattr(openai_adapter, "urlopen", lambda *_args, **_kw: _ExactResponse({}))
    monkeypatch.setattr(openai_adapter, "MAX_RESPONSE_BYTES", 8)
    with pytest.raises(openai_adapter.OpenAIAdapterError) as error:
        openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=10)
    assert str(error.value) == "OpenAI returned invalid JSON"


@pytest.mark.parametrize(
    ("model", "prompt", "key", "limit"),
    [
        ("", "prompt", "secret", 10),
        ("model", "", "secret", 10),
        ("model", "prompt", " ", 10),
        ("model", "prompt", "secret", 0),
        ("model", "prompt", "secret", -1),
    ],
)
def test_invalid_request_is_rejected_before_transport(monkeypatch, model, prompt, key, limit):
    monkeypatch.setattr(openai_adapter, "urlopen", lambda *_args, **_kw: pytest.fail("called"))
    message = (
        "OpenAI output limit must be positive"
        if limit <= 0
        else "OpenAI model, prompt, and key are required"
    )
    with pytest.raises(openai_adapter.OpenAIAdapterError) as error:
        openai_adapter.run_text_response(model, prompt, key, max_output_tokens=limit)
    assert str(error.value) == message


def test_one_output_token_is_valid(monkeypatch):
    monkeypatch.setattr(
        openai_adapter,
        "urlopen",
        lambda *_args, **_kw: _Response(
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "x"}],
                    }
                ],
            }
        ),
    )
    assert openai_adapter.run_text_response("model", "prompt", "secret", max_output_tokens=1) == "x"
