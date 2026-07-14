"""FastAPI app for the local AgentRouter REST surface (Phase P7).

Local-first and offline-safe: it classifies/routes tasks and previews execution
plans, but NEVER spawns a process (see service.execute_dry_run). Auth is optional
local mode — set AGENTROUTER_API_KEY to require an X-API-Key header.

Run: uvicorn agentrouter.server.app:app
OpenAPI: /openapi.json   Docs: /docs
"""

from __future__ import annotations

import os
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agentrouter.registry import RegistryError

from . import service
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


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Local-mode auth: open unless AGENTROUTER_API_KEY is set, then key must match."""
    expected = os.environ.get(API_KEY_ENV)
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentRouter OS — Local API",
        version="1",
        description="Local REST surface for task classification and model routing. No remote "
        "execution: dry-run only.",
        responses={"4XX": {"model": ErrorResponse}, "5XX": {"model": ErrorResponse}},
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response

    @app.exception_handler(HTTPException)
    async def http_exc_handler(_request: Request, exc: HTTPException):
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
