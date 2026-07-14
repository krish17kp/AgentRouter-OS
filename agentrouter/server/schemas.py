"""Request/response models for the local REST API (Phase P7).

Response payloads that pass through engine/classifier output verbatim are typed
as `dict` on purpose — those shapes are owned by engine.py/classifier.py and
re-modeling them here would just drift. Request bodies are validated strictly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentrouter.schema import Level


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str


class ModelSummary(BaseModel):
    vendor: str | None
    model_id: str
    key: str
    release_channel: str
    context_window: int
    host_availability: str


class HostStatusResponse(BaseModel):
    host: str
    availability: str
    reason: str


class ClassifyRequest(BaseModel):
    task: str = Field(min_length=1)
    context_tokens: int | None = Field(default=None, gt=0)
    risk: Level | None = None
    tools: list[str] | None = None


class RouteRequest(ClassifyRequest):
    prefer: str | None = None
    no_log: bool = False


class FeedbackRequest(BaseModel):
    decision_id: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    note: str | None = None


class FeedbackResponse(BaseModel):
    decision_id: str
    recorded: bool


class DryRunRequest(BaseModel):
    decision_id: str = Field(min_length=1)
