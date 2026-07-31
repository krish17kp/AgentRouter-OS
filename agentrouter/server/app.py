"""FastAPI app for the local AgentRouter REST surface (Phase P7).

Local-first and offline-safe: it classifies/routes tasks and previews execution
plans, but NEVER spawns a process (see service.execute_dry_run). Auth is optional
local mode — set AGENTROUTER_API_KEY to require an X-API-Key header.

Run: uvicorn agentrouter.server.app:app
OpenAPI: /openapi.json   Docs: /docs
"""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agentrouter import observability
from agentrouter.registry import RegistryError

from . import limits, service
from .schemas import (
    ClassifyRequest,
    DryRunRequest,
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    HostStatusResponse,
    ModelSummary,
    RouteRequest,
)

API_KEY_ENV = "AGENTROUTER_API_KEY"
REQUEST_ID_HEADER = "X-Request-ID"


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _api_key_ok(provided: str | None, expected: str | None) -> bool:
    """Constant-time key check. Open (True) when no key is configured."""
    if not expected:
        return True
    return provided is not None and hmac.compare_digest(provided, expected)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Local-mode auth: open unless AGENTROUTER_API_KEY is set, then key must match."""
    if not _api_key_ok(x_api_key, os.environ.get(API_KEY_ENV)):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentRouter OS — Local API",
        version="1",
        description="Local REST surface for task classification and model routing. No remote "
        "execution: dry-run only.",
        responses={"4XX": {"model": ErrorResponse}, "5XX": {"model": ErrorResponse}},
    )

    # Per-app in-memory stores (fresh per create_app() -> test isolation).
    rate_limiter = limits.RateLimiter()
    idempotency = limits.IdempotencyCache()

    # Middleware added LAST wraps OUTERMOST. limits_middleware is added first (inner)
    # and request_id_middleware last (outer) so X-Request-ID is set even on limits'
    # short-circuit responses (429 / idempotent replay).
    @app.middleware("http")
    async def limits_middleware(request: Request, call_next):
        # Mirror the route-level auth decision here so the cache/rate-key can never
        # outrun require_api_key: an unauthenticated request must not read or write
        # the idempotency cache, and must not get a trusted rate-limit bucket.
        expected = os.environ.get(API_KEY_ENV)
        provided = request.headers.get("X-API-Key")
        authed = _api_key_ok(provided, expected)

        # 1. Rate limit (opt-in; probes exempt). Only trust the API key as the bucket
        #    key when it actually validated — otherwise bucket by host so a rotated
        #    header can't mint unlimited buckets.
        if request.url.path not in limits.RATE_EXEMPT_PATHS:
            trusted_key = provided if (expected and authed) else None
            key = limits.client_key(trusted_key, request.client.host if request.client else None)
            allowed, retry_after = rate_limiter.check(key)
            if not allowed:
                resp = _error(429, "rate_limited", "too many requests; slow down")
                resp.headers["Retry-After"] = str(retry_after)
                return resp

        # 2. Idempotency — only for authenticated POSTs that opt in via header.
        idem = request.headers.get("Idempotency-Key")
        if request.method != "POST" or not idem or not authed:
            return await call_next(request)

        # Key namespaced by identity + path + body hash so a reused key with a
        # different payload (or a different caller) can never replay a stale/foreign
        # response.
        body_in = await request.body()
        identity = provided if expected else "local"
        cache_key = "|".join(
            [identity, idem, request.url.path, hashlib.sha256(body_in).hexdigest()]
        )
        cached = idempotency.get(cache_key)
        if cached is not None:
            replay = Response(
                content=cached.body, status_code=cached.status, media_type=cached.media_type
            )
            replay.headers["Idempotency-Replay"] = "true"
            return replay

        response = await call_next(request)
        body = b"".join([chunk async for chunk in response.body_iterator])
        # Only cache successful responses so a transient 4xx/5xx isn't pinned for the TTL.
        if 200 <= response.status_code < 300:
            # BaseHTTPMiddleware's response.media_type is always None; the real
            # content-type lives in the headers, so capture it there for the replay.
            idempotency.put(
                cache_key,
                limits.CachedResponse(
                    response.status_code, body, response.headers.get("content-type")
                ),
            )
        buffered = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        buffered.headers["Idempotency-Replay"] = "false"
        return buffered

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        observability.set_request_id(rid)
        try:
            response = await call_next(request)
        finally:
            observability.set_request_id(None)  # avoid a stale id bleeding across contexts
        response.headers[REQUEST_ID_HEADER] = rid
        return response

    # Registered on Starlette's base class so unmatched-route 404s (raised as the
    # base HTTPException, not FastAPI's subclass) also get the error envelope.
    @app.exception_handler(StarletteHTTPException)
    async def http_exc_handler(_request: Request, exc: StarletteHTTPException):
        code = {401: "unauthorized", 404: "not_found", 503: "unavailable"}.get(
            exc.status_code, "error"
        )
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {"msg": "invalid request"}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = f"{loc}: {first.get('msg')}" if loc else str(first.get("msg"))
        return _error(422, "validation_error", message)

    protected = [Depends(require_api_key)]

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready", response_model=HealthResponse, tags=["meta"])
    def ready() -> dict:
        try:
            service.load_registry()
        except RegistryError as e:
            raise HTTPException(status_code=503, detail=f"registry not ready: {e}") from e
        return {"status": "ready"}

    @app.get("/v1/models", response_model=list[ModelSummary], dependencies=protected, tags=["v1"])
    def models() -> list[dict]:
        return service.list_models()

    @app.get(
        "/v1/hosts", response_model=list[HostStatusResponse], dependencies=protected, tags=["v1"]
    )
    def hosts_() -> list[dict]:
        return service.list_hosts()

    @app.post("/v1/classify", dependencies=protected, tags=["v1"])
    def classify_(body: ClassifyRequest) -> dict:
        return service.classify_task(
            body.task,
            context_tokens=body.context_tokens,
            risk=body.risk.value if body.risk else None,
            tools=body.tools,
        )

    @app.post("/v1/route", dependencies=protected, tags=["v1"])
    def route_(body: RouteRequest) -> dict:
        return service.route_task(
            body.task,
            prefer=body.prefer,
            context_tokens=body.context_tokens,
            risk=body.risk.value if body.risk else None,
            tools=body.tools,
            no_log=body.no_log,
        )

    @app.get("/v1/decisions/{decision_id}", dependencies=protected, tags=["v1"])
    def decision_(decision_id: str) -> dict:
        payload = service.get_decision(decision_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"no decision '{decision_id}'")
        return payload

    @app.post("/v1/feedback", response_model=FeedbackResponse, dependencies=protected, tags=["v1"])
    def feedback_(body: FeedbackRequest) -> dict:
        recorded = service.save_feedback(body.decision_id, body.rating, body.note)
        if not recorded:
            raise HTTPException(status_code=404, detail=f"no decision '{body.decision_id}'")
        return {"decision_id": body.decision_id, "recorded": True}

    @app.post("/v1/execute/dry-run", dependencies=protected, tags=["v1"])
    def dry_run_(body: DryRunRequest) -> dict:
        plan = service.execute_dry_run(body.decision_id)
        if plan is None:
            raise HTTPException(status_code=404, detail=f"no decision '{body.decision_id}'")
        return plan

    return app


app = create_app()
