"""Request/response models for the local REST API (Phase P7).

Response payloads that pass through engine/classifier output verbatim are typed
as `dict` on purpose — those shapes are owned by engine.py/classifier.py and
re-modeling them here would just drift. Request bodies are validated strictly.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentrouter.schema import Level


class _Passthrough(BaseModel):
    """Documents the stable top-level keys without truncating the payload.

    The engine/classifier own these shapes, so the fields below are declared to
    give the exported contract something to protect (renaming or dropping one is
    then a detectable breaking change) while ``extra="allow"`` keeps every other
    key flowing through untouched — a strict model would silently delete fields
    from live responses.
    """

    model_config = ConfigDict(extra="allow")


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
    # additive (TASK-016): finer readiness state + concrete fix. Defaulted so
    # older clients and any caller building this model positionally still work.
    state: str = "unknown"
    remedy: str | None = None


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


# --- response envelopes for the engine/classifier-owned payloads --------------
#
# These endpoints used to be declared `-> dict`, so the exported contract said
# only "an object" and the compatibility checker could not detect a renamed or
# removed field on four of the nine operations. Declaring the stable top-level
# keys makes those changes visible; `extra="allow"` (from `_Passthrough`) means
# nothing is stripped from the wire.


class ClassifyResponse(_Passthrough):
    task_type: str | None = None
    complexity: str | None = None
    risk: str | None = None
    context_band: str | None = None
    context_tokens: int | None = None
    output_type: str | None = None
    tool_needs: list[str] | None = None
    approval_level: str | None = None
    confidence: float | None = None
    needs_clarification: bool | None = None


class RouteResponse(_Passthrough):
    task: str | None = None
    decision_id: str | None = None
    classification: dict | None = None
    recommendation: dict | None = None
    fallback: dict | None = None
    execution_route: dict | None = None
    fallback_execution_route: dict | None = None
    scores: list | None = None
    excluded: list | None = None
    gates: dict | list | None = None
    prompt: str | None = None
    weights: dict | None = None
    weight_shifts: list | None = None


class DecisionResponse(RouteResponse):
    created_at: str | None = None
    user: str | None = None


class DryRunResponse(_Passthrough):
    decision_id: str | None = None
    recommendation: dict | None = None
    execution_route: dict | None = None
    argv: list[str] | None = None
    would_execute: bool | None = None
    auto_execute_allowed: bool | None = None
    note: str | None = None
