"""Pydantic schemas — the single source of truth per MODEL_REGISTRY_SCHEMA.md."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class ReleaseChannel(str, Enum):
    stable = "stable"
    preview = "preview"
    experimental = "experimental"
    deprecated = "deprecated"


class SnapshotType(str, Enum):
    pinned = "pinned"  # a dated/immutable model id
    alias = "alias"  # a floating alias (e.g. claude-haiku-4-5)
    unknown = "unknown"


class AbilitySource(str, Enum):
    official = "official"
    benchmark = "benchmark"
    curated = "curated"
    heuristic = "heuristic"


class ExecutionMode(str, Enum):
    cli = "cli"
    api = "api"
    manual = "manual"


class Ability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coding: int = Field(ge=0, le=10)
    reasoning: int = Field(ge=0, le=10)
    writing: int = Field(ge=0, le=10)


class ExecutionTarget(BaseModel):
    """How a model can actually be run (program §Phase 1). A model may have many.

    Separates model capability (ModelEntry) from execution availability (host).
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    host: str  # claude-code | codex-cli | anthropic-api | openai-api | manual | ...
    host_model_id: str  # exact id the host expects (may differ from model_id)
    execution_mode: ExecutionMode = ExecutionMode.cli
    command_template: list[str] | None = None  # argv template; "{prompt}" is replaced
    required_command: str | None = None  # local binary that must exist (e.g. "claude")
    required_env: list[str] = []  # env vars that must be set (never printed)
    supports_noninteractive: bool = True
    supports_file_edit: bool = False
    supports_shell: bool = False


class ModelEntry(BaseModel):
    """One model in registry/models.yaml. Unknown fields are rejected (spec §3).

    Backward compatible: legacy entries use only `provider`; `vendor` defaults to
    `provider` when omitted. New entries set vendor (the model maker) and carry
    `execution_targets` (the hosts that can run it) — a distinct concept.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    provider: str
    vendor: str | None = None  # model maker; defaults to provider for legacy entries
    model_id: str
    display_name: str | None = None
    family: str | None = None
    release_channel: ReleaseChannel = ReleaseChannel.stable
    snapshot_type: SnapshotType = SnapshotType.unknown
    context_window: int = Field(gt=0)
    max_input_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int = Field(gt=0)
    pricing_tier: PricingTier
    latency_tier: LatencyTier
    # optional real pricing metadata (curated/official); pricing_tier stays the routing knob
    input_price_per_million: float | None = Field(default=None, ge=0)
    output_price_per_million: float | None = Field(default=None, ge=0)
    pricing_basis: str | None = None  # api_list | subscription | openrouter | unknown
    pricing_effective_date: date | None = None
    ability: Ability
    ability_source: AbilitySource = AbilitySource.heuristic
    ability_confidence: float | None = Field(default=None, ge=0, le=1)
    tool_support: list[str]
    vision_support: bool
    audio_support: bool = False
    video_support: bool = False
    reasoning_support: bool = False
    ideal_use_cases: list[str] = []
    avoid_use_cases: list[str] = []
    deprecation_status: DeprecationStatus
    fallback: list[str] = []
    execution_targets: list[ExecutionTarget] = []
    notes: str | None = None
    source: str | None = None  # manual | refresh | official_api | curated | heuristic
    source_url_or_identifier: str | None = None
    last_updated: date | None = None
    last_verified: date | None = None

    @model_validator(mode="after")
    def _default_vendor(self) -> ModelEntry:
        if self.vendor is None:
            object.__setattr__(self, "vendor", self.provider)
        return self

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.model_id}"

    @property
    def vendor_key(self) -> str:
        return f"{self.vendor}/{self.model_id}"

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

    # Phase P3 confidence/abstention (additive; defaults keep old constructors valid).
    confidence: float = Field(default=1.0, ge=0, le=1)
    needs_clarification: bool = False
    alternative_task_type: TaskType | None = None
    ambiguity_reason: str | None = None
