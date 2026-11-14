"""Explicit, bounded OpenAI Responses API execution for text-only decisions.

This module never runs during routing. The CLI calls it only after the recorded
decision's safety gate, provider opt-in, host readiness, and --yes checks.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
    urlopen,
)

RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_RESPONSE_BYTES = 2_000_000
MAX_OUTPUT_TOKENS = 4_096
TIMEOUT_SECONDS = 60
_DEFAULT_URLOPEN = urlopen


class OpenAIAdapterError(Exception):
    """A safe, credential-free error for the caller to display."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        return None


def _open_url(request: Request, *, timeout: int):
    """Make one request without forwarding credentials through redirects.

    Tests can replace the module-level ``urlopen`` callable with an offline
    fixture; normal execution uses an opener with redirects disabled.
    """
    if urlopen is not _DEFAULT_URLOPEN:
        return urlopen(request, timeout=timeout)  # nosec B310 - only the offline test override
    return build_opener(_NoRedirect()).open(  # nosec B310 - execution uses the fixed HTTPS URL
        request, timeout=timeout
    )


def run_text_response(model_id: str, prompt: str, api_key: str, *, max_output_tokens: int) -> str:
    """Submit one text request; never retry a possibly billable operation."""
    if not model_id or not prompt or not api_key.strip():
        raise OpenAIAdapterError("OpenAI model, prompt, and key are required")
    if max_output_tokens < 1:
        raise OpenAIAdapterError("OpenAI output limit must be positive")
    body = json.dumps(
        {
            "model": model_id,
            "input": prompt,
            "max_output_tokens": min(max_output_tokens, MAX_OUTPUT_TOKENS),
            "store": False,
            "stream": False,
        }
    ).encode("utf-8")
    request = Request(
        RESPONSES_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with _open_url(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise OpenAIAdapterError(f"OpenAI request failed with HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise OpenAIAdapterError("OpenAI request failed or timed out") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise OpenAIAdapterError("OpenAI response exceeded the size limit")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise OpenAIAdapterError("OpenAI returned invalid JSON") from None
    if not isinstance(payload, dict) or payload.get("status") != "completed":
        raise OpenAIAdapterError("OpenAI response did not complete")
    output = payload.get("output")
    if not isinstance(output, list):
        raise OpenAIAdapterError("OpenAI response had no output items")
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        if item.get("role") != "assistant" or not isinstance(item.get("content"), list):
            continue
        for content in item["content"]:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise OpenAIAdapterError("OpenAI refused this request")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    if not parts or not any(part.strip() for part in parts):
        raise OpenAIAdapterError("OpenAI response contained no text output")
    return "\n".join(parts)
