"""Pydantic schemas — the single source of truth per MODEL_REGISTRY_SCHEMA.md."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# --- enums ---------------------------------------------------------------


class PricingTier(str, Enum):
    free = "free"
    low = "low"
    medium = "medium"
    high = "high"
    frontier = "frontier"


class LatencyTier(str, Enum):
    fast = "fast"
    medium = "medium"
    slow = "slow"


class DeprecationStatus(str, Enum):
    active = "active"
    deprecated = "deprecated"
    retired = "retired"


class TaskType(str, Enum):
    coding = "coding"
    reasoning = "reasoning"
    writing = "writing"
    analysis = "analysis"
    summarization = "summarization"
    general = "general"


class Level(str, Enum):  # complexity and risk share low/medium/high
    low = "low"
    medium = "medium"
    high = "high"


class OutputType(str, Enum):
    code = "code"
    text = "text"
    code_tests = "code+tests"
    data = "data"
    plan = "plan"


class ApprovalLevel(str, Enum):
    auto = "auto"
    notify = "notify"
    human_approval_required = "human-approval-required"


class ContextBand(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


# --- registry entries ------------------------------------------------------


class Ability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coding: int = Field(ge=0, le=10)
    reasoning: int = Field(ge=0, le=10)
    writing: int = Field(ge=0, le=10)


class ModelEntry(BaseModel):
    """One model in registry/models.yaml. Unknown fields are rejected (spec §3)."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    provider: str
    model_id: str
    display_name: str | None = None
    context_window: int = Field(gt=0)
    max_input_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int = Field(gt=0)
    pricing_tier: PricingTier
    latency_tier: LatencyTier
    ability: Ability
    tool_support: list[str]
    vision_support: bool
    ideal_use_cases: list[str] = []
    avoid_use_cases: list[str] = []
    deprecation_status: DeprecationStatus
    fallback: list[str] = []
    notes: str | None = None
    source: str | None = None  # manual | refresh
    last_updated: date | None = None

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.model_id}"

    @property
    def name(self) -> str:
        return self.display_name or self.model_id


class Provider(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    adapter: str
    auth_model: str = "none"  # none | api-key | oauth | local | manual
    supports_execution: bool = False  # opt-in per provider (M6); seeds ship false
    # argv template for `agentrouter execute`; "{prompt}" is replaced with the
    # generated prompt. Only honored when supports_execution is true.
    exec_command: list[str] = []


# --- classification --------------------------------------------------------


class Classification(BaseModel):
    """The 7 canonical dimensions (ROUTING_RULES.md §1)."""

    model_config = ConfigDict(extra="forbid")

    task_type: TaskType
    complexity: Level
    risk: Level
    context_tokens: int
    context_band: ContextBand
    output_type: OutputType
    tool_needs: list[str]
    approval_level: ApprovalLevel
