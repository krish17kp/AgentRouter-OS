"""Tiny typed Python SDK for the local AgentRouter REST API (Phase P7).

    from agentrouter.sdk import AgentRouterClient
    client = AgentRouterClient("http://127.0.0.1:8000")
    client.route("summarize this PDF")

Errors from the server ({"error": {...}}) surface as AgentRouterError.
"""

from __future__ import annotations

from typing import Any

import httpx


class AgentRouterError(RuntimeError):
    """Raised for non-2xx responses; carries HTTP status and server error code."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(f"[{status_code}] {code}: {message}")
        self.status_code = status_code
        self.code = code


class AgentRouterClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ):
        headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> AgentRouterClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._client.request(method, path, **kwargs)
        if resp.is_success:
            return resp.json()
        try:
            err = resp.json().get("error", {})
        except ValueError:
            err = {}
        raise AgentRouterError(
            resp.status_code, err.get("code", "error"), err.get("message", resp.text)
        )

    # --- endpoints ---------------------------------------------------------
    def health(self) -> dict:
        return self._request("GET", "/health")

    def ready(self) -> dict:
        return self._request("GET", "/ready")

    def models(self) -> list[dict]:
        return self._request("GET", "/v1/models")

    def hosts(self) -> list[dict]:
        return self._request("GET", "/v1/hosts")

    def classify(
        self,
        task: str,
        *,
        context_tokens: int | None = None,
        risk: str | None = None,
        tools: list[str] | None = None,
    ) -> dict:
        body = _clean(task=task, context_tokens=context_tokens, risk=risk, tools=tools)
        return self._request("POST", "/v1/classify", json=body)

    def route(
        self,
        task: str,
        *,
        prefer: str | None = None,
        context_tokens: int | None = None,
        risk: str | None = None,
        tools: list[str] | None = None,
        no_log: bool = False,
    ) -> dict:
        body = _clean(
            task=task,
            prefer=prefer,
            context_tokens=context_tokens,
            risk=risk,
            tools=tools,
            no_log=no_log,
        )
        return self._request("POST", "/v1/route", json=body)

    def get_decision(self, decision_id: str) -> dict:
        return self._request("GET", f"/v1/decisions/{decision_id}")

    def feedback(self, decision_id: str, rating: int, note: str | None = None) -> dict:
        body = _clean(decision_id=decision_id, rating=rating, note=note)
        return self._request("POST", "/v1/feedback", json=body)

    def execute_dry_run(self, decision_id: str) -> dict:
        return self._request("POST", "/v1/execute/dry-run", json={"decision_id": decision_id})


def _clean(**kwargs: Any) -> dict:
    """Drop None values so server defaults apply; keep explicit False/0."""
    return {k: v for k, v in kwargs.items() if v is not None}
