"""Failure injection: what the API does when the world misbehaves (TASK-018B).

Every case asserts the same contract, because that contract is what makes a
failure survivable for a user and diagnosable for an operator:

* a **stable, typed** status and error code — never a bare 500 with no envelope;
* **no raw traceback** and no filesystem path in the response body;
* the **X-Request-ID** is retained so the response can be correlated to a log;
* no credential value anywhere in the response;
* bounded runtime — a broken dependency must not hang the request.

These are not load tests; they run fast and belong in ordinary CI.
"""

from __future__ import annotations

import os
import stat

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from agentrouter.server.app import create_app  # noqa: E402

CREDENTIAL = "sk-livekey0123456789abcdefghij"


@pytest.fixture()
def client(home):
    return TestClient(create_app(), raise_server_exceptions=False)


def assert_survivable(response, *, expected_status: int, expected_code: str, forbidden=()):
    """The shared contract every injected failure must satisfy."""
    assert response.status_code == expected_status, response.text
    body = response.json()
    assert body["error"]["code"] == expected_code, body
    assert response.headers.get("X-Request-ID"), "response is not correlatable to a log"
    # Never a traceback, never a credential, never a caller-supplied path.
    for leak in ("Traceback", 'File "', CREDENTIAL, *forbidden):
        assert leak not in response.text, f"leaked {leak!r}"


# --- the data layer is broken -------------------------------------------------


def test_registry_missing_entirely(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTROUTER_HOME", str(tmp_path / "never-initialised"))
    monkeypatch.delenv("AGENTROUTER_API_KEY", raising=False)
    c = TestClient(create_app(), raise_server_exceptions=False)
    for path in ("/ready", "/v1/models"):
        assert_survivable(
            c.get(path),
            expected_status=503,
            expected_code="registry_unavailable",
            forbidden=(str(tmp_path),),
        )


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("malformed yaml", b'models:\n  - key: x\n    token: "' + CREDENTIAL.encode() + b"\n"),
        ("non-utf8 bytes", b"models:\n  - key: \xff\xfe\xfd not utf-8\n"),
        ("wrong root type", b"- just\n- a\n- list\n"),
        ("truncated mid-write", b"models:\n  - key: partial"),
        ("empty file", b""),
    ],
)
def test_corrupt_registry_is_typed_not_a_crash(home, name, content):
    (home / "registry" / "models.yaml").write_bytes(content)
    c = TestClient(create_app(), raise_server_exceptions=False)
    response = c.get("/v1/models")
    assert response.status_code in (200, 503), f"{name}: {response.status_code}"
    if response.status_code == 503:
        assert_survivable(
            response,
            expected_status=503,
            expected_code="registry_unavailable",
            forbidden=(str(home), "models.yaml"),
        )


def test_read_only_data_directory_does_not_leak_or_crash(home):
    """A read-only home is exactly the NTFS remount hazard this project has hit."""
    c = TestClient(create_app(), raise_server_exceptions=False)
    # reads keep working
    assert c.get("/v1/models").status_code == 200

    mode = home.stat().st_mode
    os.chmod(home, stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(home, os.W_OK):  # running as root ignores the mode
            pytest.skip("cannot make the directory read-only for this user")
        response = c.post("/v1/route", json={"task": "write a haiku"})
        # Either it degrades cleanly or it refuses cleanly — never a traceback.
        assert response.status_code in (200, 500, 503), response.text
        assert response.headers.get("X-Request-ID")
        assert "Traceback" not in response.text
        assert str(home) not in response.text
    finally:
        os.chmod(home, mode)


# --- the caller misbehaves ----------------------------------------------------


def test_oversized_request_body_is_rejected_without_echoing_it(client, home):
    """An unbounded request field is a disk-fill primitive.

    `task` is echoed in the response AND persisted verbatim, so before this was
    bounded a 2 MB task produced a 4 MB response and a 4 MB database row — from
    one caller, on a service that is open by default, with no upper limit.
    """
    from agentrouter.server.schemas import MAX_TASK_CHARS

    db_before = (home / "agentrouter.db").stat().st_size
    response = client.post("/v1/route", json={"task": "A" * (MAX_TASK_CHARS + 1)})

    assert_survivable(response, expected_status=422, expected_code="validation_error")
    assert len(response.text) < 10_000, "the server echoed the oversized input back"
    assert (home / "agentrouter.db").stat().st_size == db_before, "oversized input was persisted"


def test_a_task_at_the_limit_is_still_accepted(client):
    """The bound must not break a legitimately long task."""
    from agentrouter.server.schemas import MAX_TASK_CHARS

    response = client.post("/v1/route", json={"task": "A" * MAX_TASK_CHARS})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    ("field", "body"),
    [
        ("tools", {"task": "x", "tools": ["t"] * 5_000}),
        ("prefer", {"task": "x", "prefer": "p" * 5_000}),
    ],
)
def test_other_request_fields_are_bounded_too(client, field, body):
    assert_survivable(
        client.post("/v1/route", json=body),
        expected_status=422,
        expected_code="validation_error",
    )


def test_feedback_note_is_bounded(client):
    routed = client.post("/v1/route", json={"task": "write docs"}).json()
    assert_survivable(
        client.post(
            "/v1/feedback",
            json={"decision_id": routed["decision_id"], "rating": 5, "note": "n" * 50_000},
        ),
        expected_status=422,
        expected_code="validation_error",
    )


@pytest.mark.parametrize(
    "hostile",
    [
        "\x00\x01\x02 null and control bytes",
        "line\r\nInjected-Header: yes",
        "‮ right-to-left override",
        "﻿ byte order mark",
    ],
)
def test_hostile_unicode_in_a_task_does_not_break_the_response(client, hostile):
    response = client.post("/v1/route", json={"task": hostile})
    assert response.status_code in (200, 422), response.text
    assert response.headers.get("X-Request-ID")
    assert "Traceback" not in response.text
    # a CR/LF in the payload must never become a real response header
    assert "Injected-Header" not in response.headers


def test_malformed_json_body_is_a_typed_validation_error(client):
    response = client.post(
        "/v1/route", content=b"{not json at all", headers={"content-type": "application/json"}
    )
    assert_survivable(response, expected_status=422, expected_code="validation_error")


def test_wrong_types_are_typed_validation_errors(client):
    for body in ({"task": 42}, {"task": ["a", "b"]}, {"task": "ok", "context_tokens": "many"}):
        assert_survivable(
            client.post("/v1/route", json=body),
            expected_status=422,
            expected_code="validation_error",
        )


# --- the service layer itself fails -------------------------------------------


def test_an_unexpected_internal_exception_is_typed_and_correlatable(client, monkeypatch):
    from agentrouter.server import service

    def boom(*_a, **_k):
        raise RuntimeError(f"internal detail with {CREDENTIAL} at /etc/secret.yaml")

    monkeypatch.setattr(service, "route_task", boom)
    response = client.post(
        "/v1/route", json={"task": "x"}, headers={"X-Request-ID": "trace-me-please"}
    )
    assert_survivable(
        response,
        expected_status=500,
        expected_code="internal_error",
        forbidden=("/etc/secret.yaml", "RuntimeError"),
    )
    assert response.headers["X-Request-ID"] == "trace-me-please"


def test_a_hanging_dependency_does_not_hang_the_test_suite(client, monkeypatch):
    """Bounded runtime: a slow dependency must still return, not wedge."""
    import time

    from agentrouter.server import service

    def slow(*_a, **_k):
        time.sleep(0.5)
        raise RuntimeError("slow then broken")

    monkeypatch.setattr(service, "route_task", slow)
    started = time.perf_counter()
    response = client.post("/v1/route", json={"task": "x"})
    assert time.perf_counter() - started < 10
    assert_survivable(response, expected_status=500, expected_code="internal_error")


def test_a_lone_surrogate_in_the_raw_body_is_rejected_cleanly(client):
    """A well-formed HTTP client cannot even encode this, so it is sent raw."""
    body = b'{"task": "\xed\xa0\x80 lone surrogate"}'
    response = client.post("/v1/route", content=body, headers={"content-type": "application/json"})
    assert response.status_code in (400, 422), response.text
    assert "Traceback" not in response.text
