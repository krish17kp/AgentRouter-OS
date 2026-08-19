"""Request/response models for the local REST API (Phase P7).

Request bodies are validated strictly. Responses split in two:

* models we **construct** (HealthResponse, ModelSummary, HostStatusResponse,
  FeedbackResponse) carry real types — we own the values, so a type is a promise
  we can keep;
* models that **replay** an engine or persisted payload (the `_Passthrough`
  envelopes at the bottom) declare key names only. See the comment there.
"""

from __future__ import annotations

from typing import Any

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
# These four endpoints used to be declared `-> dict`, so the exported contract
# said only "an object" and the compatibility checker could not detect a renamed
# or removed field on four of the nine operations. Declaring the stable top-level
# keys makes those changes visible; `extra="allow"` keeps everything else flowing
# through untouched.
#
# EVERY field here is `Any`, with no exceptions, and that is the whole design:
#
#   * These models do not construct their payload — they *replay* one. `/v1/route`
#     passes the engine's dict straight through, and `/v1/decisions/{id}` replays a
#     blob persisted by whatever engine version wrote the row (store.py keeps opaque
#     JSON with no schema version).
#   * So a type here is an assertion about data we did not produce and cannot
#     migrate. The first time a historical row disagrees, a working 200 becomes a
#     500 — a regression on data the user already has, which is the one failure a
#     *compatibility* change must not introduce.
#   * A single missed field is enough: `prompt` was left as `str | None` in the
#     first pass, and a decision written when `prompt` was a dict returned 500.
#     A rule with exceptions is a rule that gets one wrong, so there are none.
#
# What the contract gets from these models is therefore the **key names**, and that
# is what the checker protects: renaming or removing one is a detectable breaking
# change. Models we genuinely construct ourselves — HealthResponse, ModelSummary,
# HostStatusResponse, FeedbackResponse — keep their real types, because there we
# own the values and a type is a promise we can actually keep.


class ClassifyResponse(_Passthrough):
    task_type: Any = None
    complexity: Any = None
    risk: Any = None
    context_band: Any = None
    context_tokens: Any = None
    output_type: Any = None
    tool_needs: Any = None
    approval_level: Any = None
    confidence: Any = None
    needs_clarification: Any = None


class RouteResponse(_Passthrough):
    task: Any = None
    decision_id: Any = None
    classification: Any = None
    recommendation: Any = None
    fallback: Any = None
    execution_route: Any = None
    fallback_execution_route: Any = None
    scores: Any = None
    excluded: Any = None
    gates: Any = None
    prompt: Any = None
    weights: Any = None
    weight_shifts: Any = None


class DecisionResponse(RouteResponse):
    created_at: Any = None
    user: Any = None


class DryRunResponse(_Passthrough):
    decision_id: Any = None
    recommendation: Any = None
    execution_route: Any = None
    argv: Any = None
    would_execute: Any = None
    auto_execute_allowed: Any = None
    note: Any = None
